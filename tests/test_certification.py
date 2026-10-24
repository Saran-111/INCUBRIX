import os
import pytest
from pathlib import Path
from app.catalogue.models import DestinationRecord
from app.catalogue.importer import catalogue_store
from app.certification.harness import certification_harness
from app.certification.scheduler import recertification_scheduler

@pytest.mark.asyncio
async def test_full_certification_lifecycle_with_evidence():
    """
    Core Level: Full certification run (publish, confirm live URL, status, delete)
    with stored evidence.
    """
    dest = DestinationRecord(
        name="Certification Test Forum",
        url="https://cert-test.discourse.org",
        platform_key="discourse",
        connector_key="discourse",
        level="L0"
    )
    await catalogue_store.add_or_update(dest)

    evidence = await certification_harness.certify_destination(dest)
    
    assert evidence.verdict == "PASSED"
    assert evidence.publish_response.get("platform_post_id") is not None
    assert evidence.status_response.get("status") == "live"
    assert evidence.delete_response.get("deleted") is True
    assert evidence.duration_seconds < 10.0  # Deleted within seconds (< 10 minutes)
    
    # Check evidence file exists on disk
    assert Path(evidence.evidence_file).exists()

@pytest.mark.asyncio
async def test_recertification_scheduler_demotes_failing_destination():
    """
    Outstanding Level: Recertification re-tests destinations; a failing destination
    is demoted to L0 and generates an alert ticket.
    """
    failing_dest = DestinationRecord(
        name="Broken API Community",
        url="https://broken-api.org",
        platform_key="discourse",
        connector_key="discourse",
        level="L3"
    )
    await catalogue_store.add_or_update(failing_dest)

    from app.mocks.mock_server import mock_state
    mock_state.trigger_content_rejection = True
    try:
        evidence = await certification_harness.certify_destination(failing_dest)
        assert evidence.verdict == "FAILED"
        assert failing_dest.level == "L0"
        assert "[DEMOTED]" in (failing_dest.relevance_reason or "")
    finally:
        mock_state.reset_triggers()
