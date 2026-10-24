from typing import Optional
from app.connectors.base import (
    BaseConnector, Rendition, Destination, Connection,
    ValidationResult, PublishResult, StatusResult, DeleteResult, MetricsResult
)
from app.connectors.spec_validator import validate_rendition_against_spec
from app.core.config import settings
from app.core.errors import ErrorCodes, IncubrixAPIException
from app.mocks.mock_server import simulate_network_call

class SlackConnector(BaseConnector):
    async def validate(self, rendition: Rendition, destination: Destination, connection: Connection) -> ValidationResult:
        surface_spec = self.manifest_data["surfaces"][0]["spec"]
        violations = validate_rendition_against_spec(rendition, surface_spec)
        return ValidationResult(ok=len(violations) == 0, violations=violations)

    async def publish(self, rendition: Rendition, destination: Destination, connection: Connection, idempotency_key: str) -> PublishResult:
        val = await self.validate(rendition, destination, connection)
        if not val.ok:
            raise IncubrixAPIException(
                code=ErrorCodes.DEST_SPEC_VIOLATION,
                message="Rendition does not meet Slack message specification.",
                retryable=False,
                details=[v.model_dump() for v in val.violations]
            )

        res = await simulate_network_call(
            self.key,
            "publish",
            {"text": f"*{rendition.title}*\n{rendition.body}" if rendition.title else rendition.body}
        )
        return PublishResult(**res)

    async def get_status(self, platform_post_id: str, connection: Connection) -> StatusResult:
        res = await simulate_network_call(self.key, "get_status", {"platform_post_id": platform_post_id})
        return StatusResult(**res)

    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        res = await simulate_network_call(self.key, "delete", {"platform_post_id": platform_post_id})
        return DeleteResult(**res)

    async def fetch_metrics(self, platform_post_id: str, connection: Connection, since: Optional[str] = None) -> MetricsResult:
        res = await simulate_network_call(self.key, "fetch_metrics", {"platform_post_id": platform_post_id})
        return MetricsResult(**res)
