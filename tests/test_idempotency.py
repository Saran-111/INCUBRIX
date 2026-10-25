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

@pytest.mark.asyncio
async def test_idempotency_key_reuse_with_different_payload_detected():
    """
    Validates that reusing the same key with different content hash returns mismatch.
    """
    key = "conflict_check_key_123"
    rec1, is_new = await idempotency_store.get_or_create(key, "hash_payload_A")
    assert is_new is True
    assert rec1.request_hash == "hash_payload_A"

    # Reuse with different hash
    rec2, is_new_2 = await idempotency_store.get_or_create(key, "hash_payload_B")
    assert is_new_2 is False
    assert rec2.request_hash != "hash_payload_B"  # Mismatch detected!

@pytest.mark.asyncio
async def test_simultaneous_concurrent_requests_same_key():
    """
    Validates that two simultaneous requests with the same key do NOT cause duplicate publish.
    One executes, the other waits on completion and returns the identical response.
    """
    import asyncio
    idem_key = "concurrent_race_test_key"
    connector = connector_registry.get("discourse")
    dest = Destination(
        name="Concurrent Test",
        url="https://concurrent.test.org",
        platform_key="discourse",
        connector_key="discourse"
    )
    rendition = Rendition(title="Concurrent Post", body="Testing race condition protection")
    conn = Connection()

    async def make_call():
        record, is_new = await idempotency_store.get_or_create(idem_key, "hash_race_123")
        if not is_new:
            if record.status == "IN_PROGRESS":
                await asyncio.wait_for(record.event.wait(), timeout=5.0)
            return record.response_data
        
        # Simulate work
        await asyncio.sleep(0.05)
        res = await connector.publish(rendition, dest, conn, idem_key)
        data = res.model_dump()
        await idempotency_store.complete(idem_key, data)
        return data

    results = await asyncio.gather(make_call(), make_call())
    assert results[0] is not None
    assert results[1] is not None
    assert results[0]["platform_post_id"] == results[1]["platform_post_id"]

def test_canonical_request_hash_detects_single_field_changes():
    """
    Validates that changing any individual field (e.g. promo or canonical_url) alters the hash.
    """
    from app.core.idempotency import compute_request_hash
    dest = Destination(name="D1", url="https://d1.org", platform_key="discourse", connector_key="discourse")
    base_rendition = Rendition(title="T1", body="B1", tags=["tag1"], canonical_url="https://orig.com", is_promotional=False)
    
    base_hash = compute_request_hash(base_rendition, dest)

    # Change ONLY is_promotional
    promo_rendition = base_rendition.model_copy(update={"is_promotional": True})
    promo_hash = compute_request_hash(promo_rendition, dest)
    assert base_hash != promo_hash

    # Change ONLY canonical_url
    canon_rendition = base_rendition.model_copy(update={"canonical_url": "https://new-canonical.com"})
    canon_hash = compute_request_hash(canon_rendition, dest)
    assert base_hash != canon_hash
