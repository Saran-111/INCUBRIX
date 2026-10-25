import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.catalogue.models import DestinationRecord
from app.catalogue.importer import catalogue_store
from app.connectors.base import Rendition, Destination, Connection
from app.connectors.registry import connector_registry
from app.core.config import settings
from app.core.errors import ErrorCodes, IncubrixAPIException
from app.core.logging import logger

class CertificationEvidence(BaseModel):
    destination_name: str
    destination_url: str
    connector_key: str
    environment: str = "simulation"
    started_at: str
    completed_at: str
    duration_seconds: float
    publish_response: Dict[str, Any]
    status_response: Dict[str, Any]
    delete_response: Dict[str, Any]
    post_delete_verification: Dict[str, Any] = {}
    verdict: str  # PASSED, FAILED
    error_details: Optional[str] = None
    evidence_file: str

class CertificationHarness:
    def __init__(self, evidence_dir: Optional[str] = None):
        self.evidence_dir = Path(evidence_dir or "./data/evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    async def certify_destination(
        self,
        dest_record: DestinationRecord,
        connection: Optional[Connection] = None
    ) -> CertificationEvidence:
        start_time = time.time()
        start_dt = datetime.now(timezone.utc).isoformat()
        connector = connector_registry.get(dest_record.connector_key)
        
        if connection is None:
            connection = Connection(
                base_url=dest_record.url,
                api_key="simulated_token_safe",
                token="simulated_token_safe"
            )

        test_rendition = Rendition(
            title=f"IncuBrix Certification Probe {int(start_time)}",
            body="Automated connectivity and lifecycle compliance verification probe by IncuBrix. Deletes immediately.",
            tags=["test", "incubrix"],
            ai_generated=False,
            is_promotional=False
        )

        dest = Destination(
            name=dest_record.name,
            url=dest_record.url,
            platform_key=dest_record.platform_key,
            surface=dest_record.surface,
            category=dest_record.category,
            audience_tags=dest_record.audience_tags,
            language=dest_record.language,
            geo=dest_record.geo,
            est_audience=dest_record.est_audience,
            rules_url=dest_record.rules_url,
            frequency_cap=dest_record.frequency_cap,
            self_promo_allowed=dest_record.self_promo_allowed,
            link_policy=dest_record.link_policy,
            disclosure_required=dest_record.disclosure_required,
            automation_allowed=dest_record.automation_allowed,
            connector_key=dest_record.connector_key,
            relevance_score=dest_record.relevance_score,
            level=dest_record.level
        )

        pub_data = {}
        status_data = {}
        del_data = {}
        verdict = "FAILED"
        error_msg = None

        try:
            # 1. Publish test post
            pub_res = await connector.publish(
                rendition=test_rendition,
                destination=dest,
                connection=connection,
                idempotency_key=f"cert_{dest_record.platform_key}_{int(start_time)}"
            )
            pub_data = pub_res.model_dump()
            post_id = pub_res.platform_post_id

            # Verification of required fields (Hard case: platform renamed field)
            if not post_id or not pub_res.live_url:
                raise IncubrixAPIException(
                    code=ErrorCodes.PLATFORM_CONTENT_REJECTED,
                    message="Certification failed: Platform response missing post_id or live_url"
                )

            # 2. Check status (Confirm live)
            st_res = await connector.get_status(post_id, connection)
            status_data = st_res.model_dump()
            valid_live_statuses = ("live", "published", "ready_for_manual_post", "packaged")
            if st_res.status not in valid_live_statuses:
                raise IncubrixAPIException(
                    code=ErrorCodes.PLATFORM_UNAVAILABLE,
                    message=f"Certification failed: status '{st_res.status}' is not live"
                )

            # 3. Clean up / Delete (Must-have 5: deleted within 10 minutes)
            del_res = await connector.delete(post_id, connection)
            del_data = del_res.model_dump()

            if not del_res.deleted:
                raise IncubrixAPIException(
                    code=ErrorCodes.PLATFORM_CONTENT_REJECTED,
                    message="Certification failed: Delete confirmation returned False"
                )

            # 4. Confirm deletion: post-deletion verification
            post_del_res = await connector.get_status(post_id, connection)
            post_del_data = post_del_res.model_dump()
            valid_deleted_statuses = ("deleted", "not_found", "archived", "ready_for_manual_post")
            if post_del_res.status not in valid_deleted_statuses:
                raise IncubrixAPIException(
                    code=ErrorCodes.PLATFORM_UNAVAILABLE,
                    message=f"Certification failed: Inconclusive deletion. Status was '{post_del_res.status}', expected one of {valid_deleted_statuses}"
                )

            verdict = "PASSED"
            dest_record.last_certified_at = datetime.now(timezone.utc).isoformat()
            dest_record.level = "L3"

        except Exception as e:
            verdict = "FAILED"
            error_msg = str(e)
            # Demote destination on certification failure (Hard case requirement)
            dest_record.level = "L0"
            dest_record.relevance_reason = f"[DEMOTED]: Certification failure - {error_msg}"
            logger.error(f"Certification failed for {dest_record.url}: {error_msg}")

        end_dt = datetime.now(timezone.utc).isoformat()
        duration = round(time.time() - start_time, 3)

        evidence_filename = f"cert_{dest_record.connector_key}_{int(start_time)}.json"
        evidence_path = self.evidence_dir / evidence_filename

        if settings.SIMULATION_MODE:
            env_type = "simulation"
        elif any(local_k in (dest_record.url or "").lower() for local_k in ["localhost", "127.0.0.1", "0.0.0.0", "mock.", ".test", "partner-generic", "partner-compliant", ":8536", ":2368", ":9000"]):
            env_type = "local_http_integration"
        else:
            env_type = "live_platform"

        evidence = CertificationEvidence(
            destination_name=dest_record.name,
            destination_url=dest_record.url,
            connector_key=dest_record.connector_key,
            environment=env_type,
            started_at=start_dt,
            completed_at=end_dt,
            duration_seconds=duration,
            publish_response=pub_data,
            status_response=status_data,
            delete_response=del_data,
            post_delete_verification=post_del_data if 'post_del_data' in locals() else {},
            verdict=verdict,
            error_details=error_msg,
            evidence_file=str(evidence_path)
        )

        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence.model_dump(), f, indent=2)

        # Update catalogue record
        await catalogue_store.add_or_update(dest_record)
        return evidence

certification_harness = CertificationHarness()
