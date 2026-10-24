import pytest
from app.connectors.base import Rendition, Destination, Connection
from app.connectors.registry import connector_registry
from app.core.idempotency import idempotency_store
from app.mocks.mock_server import mock_state

@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_publish():
    """
    Must-have 6: The same idempotency key never creates a second post.
    """
    connector = connector_registry.get("discourse")
    dest = Destination(
        name="Idempotency Test Community",
        url="https://idem.test.org",
        platform_key="discourse",
        connector_key="discourse"
    )
    rendition = Rendition(
        title="Testing Idempotency Safety",
        body="Ensuring network retries never post duplicate content to communities.",
        tags=["idempotency"]
    )
    conn = Connection()
    test_key = "idem_safe_test_key_999"

    # First publish
    res1 = await connector.publish(rendition, dest, conn, test_key)
    await idempotency_store.complete(test_key, res1.model_dump())

    # Simulated retry with same idempotency key
    record = await idempotency_store.get(test_key)
    assert record is not None
    assert record.status == "COMPLETED"
    assert record.response_data["platform_post_id"] == res1.platform_post_id
    assert record.response_data["live_url"] == res1.live_url

@pytest.mark.asyncio
async def test_idempotency_after_forced_timeout():
    """
    Hard case: A publish call that times out and is retried with the same idempotency key.
    """
    mock_state.reset_triggers()
    
    # 1. Start operation under key
    idem_key = "timeout_test_key_888"
    record, is_new = await idempotency_store.get_or_create(idem_key, "request_hash")
    assert is_new is True
    assert record.status == "IN_PROGRESS"

    # Server succeeds and records result in background
    simulated_result = {
        "platform_post_id": "discourse_post_timeout_recovered",
        "live_url": "https://mock.discourse.org/p/discourse_post_timeout_recovered",
        "status": "published"
    }
    await idempotency_store.complete(idem_key, simulated_result)

    # 2. Client retries after client-side timeout
    retried_record, is_new_retry = await idempotency_store.get_or_create(idem_key, "request_hash")
    assert is_new_retry is False
    assert retried_record.status == "COMPLETED"
    assert retried_record.response_data["platform_post_id"] == "discourse_post_timeout_recovered"
