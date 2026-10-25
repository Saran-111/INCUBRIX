"""
Docker Compose Inter-Container Integration Test Suite
Validates that the service container communicates with the separate lemmy container
over the Docker Compose network (http://lemmy:8536 or host http://localhost:8536).
"""
import pytest
import httpx
from app.core.config import settings
from app.connectors.base import Rendition, Destination, Connection
from app.connectors.registry import connector_registry

@pytest.mark.asyncio
async def test_compose_lemmy_container_lifecycle():
    """
    Docker Compose Container Integration:
    Connects to the separate Lemmy container (settings.LEMMY_BASE_URL, default http://lemmy:8536 or http://localhost:8536),
    verifies inter-container network communication, and exercises the complete HTTP lifecycle:
      1. Probe /health endpoint on Compose lemmy container
      2. Publish test post -> HTTP POST /api/v3/post
      3. Verify live status -> HTTP GET /api/v3/post?id={id}
      4. Execute deletion -> HTTP POST /api/v3/post/delete
      5. Post-deletion verification -> HTTP GET /api/v3/post?id={id} returns 404/deleted
    """
    target_url = settings.LEMMY_BASE_URL.rstrip('/')
    
    # Check if the Compose Lemmy container is reachable
    is_reachable = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{target_url}/health")
            if resp.status_code == 200:
                is_reachable = True
    except Exception:
        # Also check fallback host port if LEMMY_BASE_URL was configured for inter-container
        if "lemmy:8536" in target_url:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get("http://localhost:8536/health")
                    if resp.status_code == 200:
                        target_url = "http://localhost:8536"
                        is_reachable = True
            except Exception:
                is_reachable = False

    if not is_reachable:
        pytest.skip(f"Docker Compose lemmy container is not running or unreachable at {target_url}. Run 'docker compose up -d' to execute.")

    connector = connector_registry.get("lemmy")
    dest = Destination(
        name="Compose Lemmy Container",
        url=target_url,
        platform_key="lemmy",
        connector_key="lemmy",
        custom_params={"community_id": 1}
    )
    conn = Connection(base_url=target_url, token="compose_integration_token")
    rendition = Rendition(
        title="Compose Container Integration Probe",
        body="Testing inter-container HTTP lifecycle between service and lemmy containers."
    )

    orig_mode = settings.SIMULATION_MODE
    settings.SIMULATION_MODE = False
    try:
        # 1. Publish to Compose container
        pub = await connector.publish(rendition, dest, conn, "compose_inter_container_01")
        assert pub.platform_post_id is not None
        assert pub.status == "published"
        assert target_url in pub.live_url

        # 2. Query live status from Compose container
        st = await connector.get_status(pub.platform_post_id, conn)
        assert st.status == "live"
        assert st.live_url == f"{target_url}/post/{pub.platform_post_id}"

        # 3. Execute deletion on Compose container
        del_res = await connector.delete(pub.platform_post_id, conn)
        assert del_res.deleted is True

        # 4. Post-deletion verification (container returns 404, connector returns 'deleted')
        post_del = await connector.get_status(pub.platform_post_id, conn)
        assert post_del.status == "deleted"
    finally:
        settings.SIMULATION_MODE = orig_mode
