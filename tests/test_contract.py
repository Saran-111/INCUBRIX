import pytest
from app.connectors.base import Rendition, Destination, Connection
from app.connectors.registry import connector_registry

@pytest.mark.asyncio
async def test_all_connectors_registered_and_manifests_valid():
    """Verify all 6 Core + 3 Advanced connectors are registered and have valid manifests."""
    required_keys = [
        "discourse", "lemmy", "devto", "ghost", "webhook_hmac", "assisted",
        "hashnode", "slack", "mailchimp"
    ]
    manifests = {m["key"]: m for m in connector_registry.list_all()}
    
    for key in required_keys:
        assert key in manifests, f"Missing manifest for connector {key}"
        manifest = manifests[key]
        assert "version" in manifest
        assert "tier" in manifest
        assert "auth" in manifest
        assert "surfaces" in manifest
        assert "capabilities" in manifest

@pytest.mark.asyncio
@pytest.mark.parametrize("connector_key", [
    "discourse", "lemmy", "devto", "ghost", "webhook_hmac", "assisted",
    "hashnode", "slack", "mailchimp"
])
async def test_connector_contract_lifecycle(connector_key):
    """
    Appendix A contract test suite:
    Validates validate(), publish(), get_status(), delete() for every connector.
    """
    connector = connector_registry.get(connector_key)
    dest = Destination(
        name=f"Test {connector_key}",
        url=f"https://test.{connector_key}.org",
        platform_key=connector_key,
        connector_key=connector_key
    )
    conn = Connection()
    rendition = Rendition(
        title="Valid Test Title for Distribution",
        body="This is a sufficiently long test body that satisfies all minimum character requirements for validation.",
        tags=["test", "incubrix"]
    )

    # 1. validate
    val_res = await connector.validate(rendition, dest, conn)
    assert val_res.ok is True, f"Validation failed for {connector_key}: {val_res.violations}"

    # 2. publish
    pub_res = await connector.publish(rendition, dest, conn, f"idem_{connector_key}")
    assert pub_res.platform_post_id is not None
    assert pub_res.live_url is not None
    assert pub_res.status in ("published", "ready_for_manual_post")

    # 3. get_status
    st_res = await connector.get_status(pub_res.platform_post_id, conn)
    assert st_res.status in ("live", "ready_for_manual_post")

    # 4. delete
    del_res = await connector.delete(pub_res.platform_post_id, conn)
    assert del_res.deleted is True

@pytest.mark.asyncio
async def test_webhook_hmac_unsupported_receiver_lifecycle_fails(monkeypatch):
    """
    Validates that in non-simulation mode, an unverified webhook receiver
    (e.g., returning 501 Not Implemented or missing status field) explicitly raises DEST_SPEC_VIOLATION,
    and NEVER returns a fabricated 'live' status or unverified deleted=True.
    """
    from unittest.mock import AsyncMock, MagicMock
    from app.core.config import settings
    from app.core.errors import ErrorCodes, IncubrixAPIException
    import httpx

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    connector = connector_registry.get("webhook_hmac")
    conn = Connection(base_url="https://partner-generic.com/webhook", secret="test_secret")

    # 1. Receiver returns 501 Not Implemented on status probe
    mock_resp_501 = MagicMock(spec=httpx.Response)
    mock_resp_501.status_code = 501
    mock_resp_501.text = "Not Implemented"
    mock_resp_501.headers = {"content-type": "text/plain"}

    mock_post = AsyncMock(return_value=mock_resp_501)
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    with pytest.raises(IncubrixAPIException) as exc_info:
        await connector.get_status("wh_test_123", conn)
    assert exc_info.value.code == ErrorCodes.DEST_SPEC_VIOLATION
    assert "unsupported" in exc_info.value.message.lower()

    # 2. Receiver returns 501 on delete probe
    with pytest.raises(IncubrixAPIException) as exc_info_del:
        await connector.delete("wh_test_123", conn)
    assert exc_info_del.value.code == ErrorCodes.DEST_SPEC_VIOLATION
    assert "unsupported" in exc_info_del.value.message.lower()

@pytest.mark.asyncio
async def test_webhook_hmac_verified_receiver_lifecycle_succeeds(monkeypatch):
    """
    Validates that in non-simulation mode, when the partner receiver conforms to the
    IncuBrix verification contract (signed POST with explicit status/deleted fields),
    status and deletion return verified results.
    """
    from unittest.mock import AsyncMock, MagicMock
    from app.core.config import settings
    import httpx

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    connector = connector_registry.get("webhook_hmac")
    conn = Connection(base_url="https://partner-compliant.com/webhook", secret="test_secret")

    # Mock receiver status response: 200 OK with {"status": "live", "live_url": "https://..."}
    mock_resp_status = MagicMock(spec=httpx.Response)
    mock_resp_status.status_code = 200
    mock_resp_status.headers = {"content-type": "application/json"}
    mock_resp_status.json = MagicMock(return_value={"status": "live", "live_url": "https://partner-compliant.com/posts/wh_123"})

    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp_status))
    st = await connector.get_status("wh_123", conn)
    assert st.status == "live"
    assert "partner-compliant.com" in st.live_url

    # Mock receiver delete response: 200 OK with {"deleted": true}
    mock_resp_del = MagicMock(spec=httpx.Response)
    mock_resp_del.status_code = 200
    mock_resp_del.headers = {"content-type": "application/json"}
    mock_resp_del.json = MagicMock(return_value={"deleted": True})

    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp_del))
    d = await connector.delete("wh_123", conn)
    assert d.deleted is True

