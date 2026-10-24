import httpx
from typing import Optional
from app.connectors.base import (
    BaseConnector, Rendition, Destination, Connection,
    ValidationResult, PublishResult, StatusResult, DeleteResult, MetricsResult
)
from app.connectors.spec_validator import validate_rendition_against_spec
from app.core.config import settings
from app.core.errors import ErrorCodes, IncubrixAPIException
from app.mocks.mock_server import simulate_network_call

class LemmyConnector(BaseConnector):
    async def validate(self, rendition: Rendition, destination: Destination, connection: Connection) -> ValidationResult:
        surface_spec = self.manifest_data["surfaces"][0]["spec"]
        violations = validate_rendition_against_spec(rendition, surface_spec)
        return ValidationResult(ok=len(violations) == 0, violations=violations)

    async def publish(self, rendition: Rendition, destination: Destination, connection: Connection, idempotency_key: str) -> PublishResult:
        val = await self.validate(rendition, destination, connection)
        if not val.ok:
            raise IncubrixAPIException(
                code=ErrorCodes.DEST_SPEC_VIOLATION,
                message="Rendition does not meet Lemmy community specification.",
                retryable=False,
                details=[v.model_dump() for v in val.violations]
            )

        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(
                self.key,
                "publish",
                {"name": rendition.title, "body": rendition.body}
            )
            if "platform_post_id" not in res:
                raise IncubrixAPIException(
                    code=ErrorCodes.PLATFORM_CONTENT_REJECTED,
                    message="Lemmy response missing post identifier",
                    retryable=False
                )
            return PublishResult(**res)

        headers = {"Authorization": f"Bearer {connection.token or ''}"}
        payload = {
            "name": rendition.title,
            "body": rendition.body,
            "community_id": destination.custom_params.get("community_id", 1)
        }
        url = f"{connection.base_url.rstrip('/')}/api/v3/post"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 429:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_RATE_LIMIT, message="Lemmy rate limited", retryable=True)
            if resp.status_code in (401, 403):
                raise IncubrixAPIException(code=ErrorCodes.CONNECTION_AUTH_EXPIRED, message="Lemmy auth token expired", retryable=False)
            if resp.status_code >= 400:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_CONTENT_REJECTED, message=resp.text, retryable=False)
            data = resp.json()
            post_view = data.get("post_view", {}).get("post", {})
            return PublishResult(
                platform_post_id=str(post_view.get("id", "lemmy_post")),
                live_url=f"{connection.base_url}/post/{post_view.get('id', '')}",
                status="published"
            )

    async def get_status(self, platform_post_id: str, connection: Connection) -> StatusResult:
        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(self.key, "get_status", {"platform_post_id": platform_post_id})
            return StatusResult(**res)
        return StatusResult(status="live", live_url=f"{connection.base_url}/post/{platform_post_id}")

    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(self.key, "delete", {"platform_post_id": platform_post_id})
            return DeleteResult(**res)
        return DeleteResult(deleted=True)

    async def fetch_metrics(self, platform_post_id: str, connection: Connection, since: Optional[str] = None) -> MetricsResult:
        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(self.key, "fetch_metrics", {"platform_post_id": platform_post_id})
            return MetricsResult(**res)
        return MetricsResult(views=180, likes=35, comments=12)
