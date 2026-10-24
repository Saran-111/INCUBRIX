import pytest
from app.connectors.base import Rendition, Destination, Connection
from app.connectors.registry import connector_registry
from app.core.errors import ErrorCodes, IncubrixAPIException
from app.mocks.mock_server import mock_state
from app.certification.harness import certification_harness
from app.catalogue.models import DestinationRecord
from app.catalogue.importer import import_destinations_from_csv

@pytest.mark.asyncio
async def test_hard_case_rate_limit_429_with_reset_time():
    """Hard case: A 429 response with a reset time."""
    connector = connector_registry.get("discourse")
    dest = Destination(name="Forum", url="https://forum.org", platform_key="discourse", connector_key="discourse")
    rendition = Rendition(title="Rate Limit Probe", body="Testing rate limit backoff handling gracefully.")
    
    mock_state.trigger_429 = True
    mock_state.retry_after_seconds = 5
    try:
        with pytest.raises(IncubrixAPIException) as exc_info:
            await connector.publish(rendition, dest, Connection(), "rate_limit_probe")
        assert exc_info.value.code == ErrorCodes.PLATFORM_RATE_LIMIT
        assert exc_info.value.retryable is True
        assert exc_info.value.details.get("retry_after") == 5
    finally:
        mock_state.reset_triggers()

@pytest.mark.asyncio
async def test_hard_case_expired_token_401():
    """Hard case: Expired token mapped to CONNECTION_AUTH_EXPIRED."""
    connector = connector_registry.get("discourse")
    dest = Destination(name="Forum", url="https://forum.org", platform_key="discourse", connector_key="discourse")
    rendition = Rendition(title="Auth Probe", body="Testing auth token expiration.")
    
    mock_state.trigger_expired_token = True
    try:
        with pytest.raises(IncubrixAPIException) as exc_info:
            await connector.publish(rendition, dest, Connection(), "auth_probe")
        assert exc_info.value.code == ErrorCodes.CONNECTION_AUTH_EXPIRED
        assert exc_info.value.retryable is False
    finally:
        mock_state.reset_triggers()

@pytest.mark.asyncio
async def test_hard_case_content_rejected():
    """Hard case: Content rejected by platform mapped to PLATFORM_CONTENT_REJECTED."""
    connector = connector_registry.get("discourse")
    dest = Destination(name="Forum", url="https://forum.org", platform_key="discourse", connector_key="discourse")
    rendition = Rendition(title="Spam Content", body="Spam content that gets blocked by community filter.")
    
    mock_state.trigger_content_rejection = True
    try:
        with pytest.raises(IncubrixAPIException) as exc_info:
            await connector.publish(rendition, dest, Connection(), "spam_probe")
        assert exc_info.value.code == ErrorCodes.PLATFORM_CONTENT_REJECTED
        assert exc_info.value.retryable is False
    finally:
        mock_state.reset_triggers()

@pytest.mark.asyncio
async def test_hard_case_renamed_field_fails_certification_and_demotes():
    """
    Hard case: A platform that renames a field in its API:
    Certification must fail and destination must be demoted.
    """
    dest = DestinationRecord(
        name="API Schema Drift Community",
        url="https://drift.test.org",
        platform_key="discourse",
        connector_key="discourse",
        level="L3"
    )
    mock_state.trigger_renamed_field = True
    try:
        evidence = await certification_harness.certify_destination(dest)
        assert evidence.verdict == "FAILED"
        assert dest.level == "L0"
        assert "[DEMOTED]" in dest.relevance_reason
    finally:
        mock_state.reset_triggers()

@pytest.mark.asyncio
async def test_hard_case_title_body_longer_than_allowed():
    """Hard case: Title or body longer than destination allows."""
    connector = connector_registry.get("discourse")
    dest = Destination(name="Forum", url="https://forum.org", platform_key="discourse", connector_key="discourse")
    
    # Title exceeding 255 chars
    huge_title = "A" * 300
    rendition = Rendition(title=huge_title, body="Normal valid body content.")
    
    with pytest.raises(IncubrixAPIException) as exc_info:
        await connector.publish(rendition, dest, Connection(), "huge_title")
    assert exc_info.value.code == ErrorCodes.DEST_SPEC_VIOLATION
    assert exc_info.value.retryable is False
    assert any(v["field"] == "title" for v in exc_info.value.details)

@pytest.mark.asyncio
async def test_hard_case_csv_duplicates_bad_urls_mixed_languages():
    """Hard case: A CSV with duplicates, bad URLs and mixed languages."""
    csv_sample = """name,url,platform_key,connector_key,language
Community 1,https://valid-community.org,discourse,discourse,en
Community 1 Dup,https://valid-community.org/,discourse,discourse,en
Bad URL Comm,htp:/brokenurl,discourse,discourse,es
Japanese Forum,https://tokyo-tech.jp,discourse,discourse,ja
Missing Name,,discourse,discourse,en
"""
    report = await import_destinations_from_csv(csv_sample)
    assert report.total_rows == 5
    assert report.valid_imported == 2  # Community 1 and Japanese Forum
    assert report.duplicates_skipped == 1  # Duplicate normalized URL
    assert report.errors_count == 2  # Bad URL and Missing Name
    assert len(report.row_errors) == 2
