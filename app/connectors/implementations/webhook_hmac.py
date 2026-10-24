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
        if settings.SIMULATION_MODE:
            res = await simulate_network_call(self.key, "get_status", {"platform_post_id": platform_post_id})
            return StatusResult(**res)
        return StatusResult(status="live", live_url=connection.base_url or "https://partner.com")

    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        if settings.SIMULATION_MODE:
            res = await simulate_network_call(self.key, "delete", {"platform_post_id": platform_post_id})
            return DeleteResult(**res)
        return DeleteResult(deleted=True)
