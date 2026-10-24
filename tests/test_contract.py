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
