import httpx
from typing import Optional
from app.connectors.base import (
    BaseConnector, Rendition, Destination, Connection,
    ValidationResult, PublishResult, StatusResult, DeleteResult
)
from app.connectors.spec_validator import validate_rendition_against_spec
from app.core.config import settings
from app.core.errors import ErrorCodes, IncubrixAPIException
from app.core.security import sign_json_payload
from app.mocks.mock_server import simulate_network_call

class WebhookHmacConnector(BaseConnector):
    async def validate(self, rendition: Rendition, destination: Destination, connection: Connection) -> ValidationResult:
        surface_spec = self.manifest_data["surfaces"][0]["spec"]
        violations = validate_rendition_against_spec(rendition, surface_spec)
        return ValidationResult(ok=len(violations) == 0, violations=violations)

    async def publish(self, rendition: Rendition, destination: Destination, connection: Connection, idempotency_key: str) -> PublishResult:
        val = await self.validate(rendition, destination, connection)
        if not val.ok:
            raise IncubrixAPIException(
                code=ErrorCodes.DEST_SPEC_VIOLATION,
                message="Rendition does not meet Webhook specification.",
                retryable=False,
                details=[v.model_dump() for v in val.violations]
            )

        target_url = connection.base_url or destination.url
        secret = connection.secret or settings.HMAC_SECRET

        payload = {
            "event": "content.publish",
            "destination": destination.name,
            "title": rendition.title,
            "body": rendition.body,
            "media_urls": rendition.media_urls,
            "tags": rendition.tags,
            "idempotency_key": idempotency_key
        }

        if settings.SIMULATION_MODE or "partner.test" in target_url:
            res = await simulate_network_call(self.key, "publish", payload)
            return PublishResult(**res)

        serialized_body, signature = sign_json_payload(payload, secret)
        headers = {
            "Content-Type": "application/json",
            settings.WEBHOOK_SIGNATURE_HEADER: signature,
            "Idempotency-Key": idempotency_key
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(target_url, content=serialized_body, headers=headers)
            if resp.status_code == 429:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_RATE_LIMIT, message="Webhook endpoint rate limited", retryable=True)
            if resp.status_code in (401, 403):
                raise IncubrixAPIException(code=ErrorCodes.CONNECTION_AUTH_EXPIRED, message="Partner HMAC verification failed", retryable=False)
            if resp.status_code >= 400:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_CONTENT_REJECTED, message=resp.text, retryable=False)
            
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            post_id = str(data.get("id", f"wh_{idempotency_key[:8]}"))
            return PublishResult(
                platform_post_id=post_id,
                live_url=target_url,
                status="published"
            )

    async def get_status(self, platform_post_id: str, connection: Connection) -> StatusResult:
        target_url = connection.base_url
        if settings.SIMULATION_MODE:
            res = await simulate_network_call(self.key, "get_status", {"platform_post_id": platform_post_id})
            return StatusResult(**res)
        
        if not target_url:
            raise IncubrixAPIException(
                code=ErrorCodes.DEST_SPEC_VIOLATION,
                message="Receiver status verification unsupported: No receiver base_url configured."
            )

        # Real HTTP HMAC Status Verification Probe:
        # Requires the receiver to implement the IncuBrix status verification contract
        secret = connection.secret or settings.HMAC_SECRET
        payload = {"event": "content.status", "platform_post_id": platform_post_id}
        serialized, sig = sign_json_payload(payload, secret)
        headers = {
            "Content-Type": "application/json",
            settings.WEBHOOK_SIGNATURE_HEADER: sig
        }

        status_url = f"{target_url.rstrip('/')}/status"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(status_url, content=serialized, headers=headers)
                if resp.status_code == 200:
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    verified_status = data.get("status")
                    if not verified_status:
                        raise IncubrixAPIException(
                            code=ErrorCodes.DEST_SPEC_VIOLATION,
                            message="Receiver status verification unsupported: Response missing explicit 'status' field."
                        )
                    return StatusResult(
                        status=verified_status,
                        live_url=data.get("live_url", target_url)
                    )
                elif resp.status_code == 404:
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    if data.get("status") == "deleted" or data.get("error") == "not_found":
                        return StatusResult(status="deleted", live_url="")
                    raise IncubrixAPIException(
                        code=ErrorCodes.DEST_SPEC_VIOLATION,
                        message="Receiver status verification unsupported: Endpoint returned 404 without contract verification."
                    )
                elif resp.status_code in (405, 501):
                    raise IncubrixAPIException(
                        code=ErrorCodes.DEST_SPEC_VIOLATION,
                        message="Receiver status verification unsupported: Endpoint does not implement status contract."
                    )
                else:
                    raise IncubrixAPIException(
                        code=ErrorCodes.PLATFORM_UNAVAILABLE,
                        message=f"Receiver status verification failed with HTTP {resp.status_code}",
                        retryable=True
                    )
            except httpx.RequestError as exc:
                raise IncubrixAPIException(
                    code=ErrorCodes.PLATFORM_UNAVAILABLE,
                    message=f"Failed to reach receiver for status verification: {exc}",
                    retryable=True
                )

    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        target_url = connection.base_url
        if settings.SIMULATION_MODE:
            res = await simulate_network_call(self.key, "delete", {"platform_post_id": platform_post_id})
            return DeleteResult(**res)

        if not target_url:
            raise IncubrixAPIException(
                code=ErrorCodes.DEST_SPEC_VIOLATION,
                message="Receiver deletion unsupported: No receiver base_url configured."
            )

        secret = connection.secret or settings.HMAC_SECRET
        payload = {"event": "content.delete", "platform_post_id": platform_post_id}
        serialized, sig = sign_json_payload(payload, secret)
        headers = {
            "Content-Type": "application/json",
            settings.WEBHOOK_SIGNATURE_HEADER: sig
        }

        delete_url = f"{target_url.rstrip('/')}/delete"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(delete_url, content=serialized, headers=headers)
                if resp.status_code in (200, 204):
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    if "deleted" in data:
                        return DeleteResult(deleted=bool(data["deleted"]))
                    elif resp.status_code == 204:
                        return DeleteResult(deleted=True)
                    else:
                        raise IncubrixAPIException(
                            code=ErrorCodes.DEST_SPEC_VIOLATION,
                            message="Receiver deletion unsupported: Response missing explicit deletion confirmation."
                        )
                elif resp.status_code == 404:
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    if data.get("status") == "deleted" or data.get("deleted") is True or data.get("error") == "not_found":
                        return DeleteResult(deleted=True)
                    raise IncubrixAPIException(
                        code=ErrorCodes.DEST_SPEC_VIOLATION,
                        message="Receiver deletion unsupported: Endpoint returned 404 without contract verification."
                    )
                elif resp.status_code in (405, 501):
                    raise IncubrixAPIException(
                        code=ErrorCodes.DEST_SPEC_VIOLATION,
                        message="Receiver deletion unsupported: Partner endpoint does not implement deletion contract."
                    )
                else:
                    raise IncubrixAPIException(
                        code=ErrorCodes.PLATFORM_UNAVAILABLE,
                        message=f"Webhook deletion verification failed with HTTP {resp.status_code}",
                        retryable=True
                    )
            except httpx.RequestError as exc:
                raise IncubrixAPIException(
                    code=ErrorCodes.PLATFORM_UNAVAILABLE,
                    message=f"Failed to reach receiver for deletion: {exc}",
                    retryable=True
                )
