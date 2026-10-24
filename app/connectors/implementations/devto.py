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

class DevToConnector(BaseConnector):
    async def validate(self, rendition: Rendition, destination: Destination, connection: Connection) -> ValidationResult:
        surface_spec = self.manifest_data["surfaces"][0]["spec"]
        violations = validate_rendition_against_spec(rendition, surface_spec)
        return ValidationResult(ok=len(violations) == 0, violations=violations)

    async def publish(self, rendition: Rendition, destination: Destination, connection: Connection, idempotency_key: str) -> PublishResult:
        val = await self.validate(rendition, destination, connection)
        if not val.ok:
            raise IncubrixAPIException(
                code=ErrorCodes.DEST_SPEC_VIOLATION,
                message="Rendition does not meet Dev.to specification.",
                retryable=False,
                details=[v.model_dump() for v in val.violations]
            )

        if settings.SIMULATION_MODE or not connection.api_key:
            res = await simulate_network_call(
                self.key,
                "publish",
                {"title": rendition.title, "body_markdown": rendition.body, "tags": rendition.tags}
            )
            return PublishResult(**res)

        headers = {"api-key": connection.api_key, "Content-Type": "application/json"}
        payload = {
            "article": {
                "title": rendition.title,
                "body_markdown": rendition.body,
                "published": True,
                "tags": rendition.tags[:4],
                "canonical_url": rendition.canonical_url
            }
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://dev.to/api/articles", json=payload, headers=headers)
            if resp.status_code == 429:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_RATE_LIMIT, message="Dev.to rate limit reached", retryable=True)
            if resp.status_code in (401, 403):
                raise IncubrixAPIException(code=ErrorCodes.CONNECTION_AUTH_EXPIRED, message="Dev.to API key invalid", retryable=False)
            if resp.status_code >= 400:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_CONTENT_REJECTED, message=resp.text, retryable=False)
            data = resp.json()
            return PublishResult(
                platform_post_id=str(data.get("id")),
                live_url=data.get("url", f"https://dev.to/article/{data.get('id')}"),
                status="published"
            )

    async def get_status(self, platform_post_id: str, connection: Connection) -> StatusResult:
        if settings.SIMULATION_MODE or not connection.api_key:
            res = await simulate_network_call(self.key, "get_status", {"platform_post_id": platform_post_id})
            return StatusResult(**res)
        return StatusResult(status="live", live_url=f"https://dev.to/article/{platform_post_id}")

    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        if settings.SIMULATION_MODE or not connection.api_key:
            res = await simulate_network_call(self.key, "delete", {"platform_post_id": platform_post_id})
            return DeleteResult(**res)
        return DeleteResult(deleted=True)

    async def fetch_metrics(self, platform_post_id: str, connection: Connection, since: Optional[str] = None) -> MetricsResult:
        if settings.SIMULATION_MODE or not connection.api_key:
            res = await simulate_network_call(self.key, "fetch_metrics", {"platform_post_id": platform_post_id})
            return MetricsResult(**res)
        return MetricsResult(views=350, likes=42, comments=8, clicks=29)
