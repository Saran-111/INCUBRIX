import uuid
from typing import Optional
from app.connectors.base import (
    BaseConnector, Rendition, Destination, Connection,
    ValidationResult, PublishResult, StatusResult, DeleteResult,
    AssistPackResult, AssistFile, ChecklistItem
)
from app.connectors.spec_validator import validate_rendition_against_spec
from app.core.errors import ErrorCodes, IncubrixAPIException

class AssistedConnector(BaseConnector):
    async def validate(self, rendition: Rendition, destination: Destination, connection: Connection) -> ValidationResult:
        surface_spec = self.manifest_data["surfaces"][0]["spec"]
        violations = validate_rendition_against_spec(rendition, surface_spec)
        return ValidationResult(ok=len(violations) == 0, violations=violations)

    async def build_assist_pack(self, rendition: Rendition, destination: Destination) -> AssistPackResult:
        files = []
        for i, url in enumerate(rendition.media_urls):
            files.append(AssistFile(
                url=url,
                type="image" if url.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) else "media",
                filename=f"asset_{i+1}_{url.split('/')[-1]}"
            ))

        # Build checklist based on destination rules
        checklist = [
            ChecklistItem(task="Copy formatted text to clipboard", checked=False),
            ChecklistItem(task="Open destination submission page", checked=False),
            ChecklistItem(task=f"Verify {destination.name} rule guidelines at {destination.rules_url or destination.url}", checked=False),
        ]
        
        if not destination.self_promo_allowed:
            checklist.append(ChecklistItem(task="Ensure post contains NO self-promotional or commercial pitches", checked=False))
            
        if destination.disclosure_required or rendition.ai_generated:
            checklist.append(ChecklistItem(task="Add mandatory AI content disclosure label to post header/footer", checked=False))

        if destination.link_policy == "restricted":
            checklist.append(ChecklistItem(task="Ensure links are only placed in comments or authorized bio section", checked=False))

        # Deep link direct to community posting URL if available
        deep_link = destination.url
        if "reddit.com" in destination.url:
            deep_link = f"{destination.url.rstrip('/')}/submit"
        elif "facebook.com" in destination.url:
            deep_link = destination.url

        return AssistPackResult(
            files=files,
            caption=f"{rendition.title}\n\n{rendition.body}" if rendition.title else rendition.body,
            deep_link=deep_link,
            checklist=checklist
        )

    async def publish(self, rendition: Rendition, destination: Destination, connection: Connection, idempotency_key: str) -> PublishResult:
        # For assisted connector, publish generates and packages the ready-to-post pack
        pack = await self.build_assist_pack(rendition, destination)
        pack_id = f"pack_{uuid.uuid4().hex[:10]}"
        return PublishResult(
            platform_post_id=pack_id,
            live_url=pack.deep_link,
            status="ready_for_manual_post"
        )

    async def get_status(self, platform_post_id: str, connection: Connection) -> StatusResult:
        return StatusResult(status="ready_for_manual_post", live_url=None)

    async def delete(self, platform_post_id: str, connection: Connection) -> DeleteResult:
        return DeleteResult(deleted=True)
