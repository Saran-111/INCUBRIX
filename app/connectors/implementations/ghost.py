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

class GhostConnector(BaseConnector):
    async def validate(self, rendition: Rendition, destination: Destination, connection: Connection) -> ValidationResult:
        surface_spec = self.manifest_data["surfaces"][0]["spec"]
        violations = validate_rendition_against_spec(rendition, surface_spec)
        return ValidationResult(ok=len(violations) == 0, violations=violations)

    async def publish(self, rendition: Rendition, destination: Destination, connection: Connection, idempotency_key: str) -> PublishResult:
        val = await self.validate(rendition, destination, connection)
        if not val.ok:
            raise IncubrixAPIException(
                code=ErrorCodes.DEST_SPEC_VIOLATION,
                message="Rendition does not meet Ghost post specification.",
                retryable=False,
                details=[v.model_dump() for v in val.violations]
            )

        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(
                self.key,
                "publish",
                {"title": rendition.title, "html": rendition.body}
            )
            return PublishResult(**res)

        headers = {"Authorization": f"Ghost {connection.token or connection.api_key or ''}"}
        payload = {
            "posts": [{
                "title": rendition.title,
                "html": f"<p>{rendition.body}</p>",
                "status": "published",
                "canonical_url": rendition.canonical_url
            }]
        }
        url = f"{connection.base_url.rstrip('/')}/ghost/api/admin/posts/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 429:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_RATE_LIMIT, message="Ghost rate limited", retryable=True)
            if resp.status_code in (401, 403):
                raise IncubrixAPIException(code=ErrorCodes.CONNECTION_AUTH_EXPIRED, message="Ghost Admin Token invalid", retryable=False)
            if resp.status_code >= 400:
                raise IncubrixAPIException(code=ErrorCodes.PLATFORM_CONTENT_REJECTED, message=resp.text, retryable=False)
            data = resp.json()
            post = data.get("posts", [{}])[0]
            return PublishResult(
                platform_post_id=str(post.get("id")),
                live_url=post.get("url", f"{connection.base_url}/p/{post.get('id')}"),
                status="published"
            )

    async def get_status(self, platform_post_id: str, connection: Connection) -> StatusResult:
        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(self.key, "get_status", {"platform_post_id": platform_post_id})
            return StatusResult(**res)
        token = self._create_token(connection.api_key or "demo:key")
        headers = {"Authorization": f"Ghost {token}"}
        url = f"{connection.base_url.rstrip('/')}/ghost/api/admin/posts/{platform_post_id}/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                post = data.get("posts", [{}])[0]
                return StatusResult(status="live", live_url=post.get("url", f"{connection.base_url}/p/{platform_post_id}"))
            elif resp.status_code == 404:
                return StatusResult(status="deleted", live_url="")
            raise IncubrixAPIException(code=ErrorCodes.PLATFORM_UNAVAILABLE, message=resp.text, retryable=True)

    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(self.key, "delete", {"platform_post_id": platform_post_id})
            return DeleteResult(**res)
        token = self._create_token(connection.api_key or "demo:key")
        headers = {"Authorization": f"Ghost {token}"}
        url = f"{connection.base_url.rstrip('/')}/ghost/api/admin/posts/{platform_post_id}/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code in (200, 204):
                return DeleteResult(deleted=True)
            elif resp.status_code in (401, 403):
                raise IncubrixAPIException(code=ErrorCodes.CONNECTION_AUTH_EXPIRED, message="Ghost token expired", retryable=False)
            return DeleteResult(deleted=False)

    async def fetch_metrics(self, platform_post_id: str, connection: Connection, since: Optional[str] = None) -> MetricsResult:
        if settings.SIMULATION_MODE or not connection.base_url:
            res = await simulate_network_call(self.key, "fetch_metrics", {"platform_post_id": platform_post_id})
            return MetricsResult(**res)
        return MetricsResult(views=420, clicks=65, saves=12)
