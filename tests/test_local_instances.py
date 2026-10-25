import asyncio
import http.server
import socketserver
import threading
import pytest
from app.core.config import settings
from app.connectors.base import Rendition, Destination, Connection
from app.connectors.registry import connector_registry
from app.mocks.lemmy_service import StatefulLemmyHandler

@pytest.fixture(scope="module")
def lemmy_test_server():
    """Starts a local stateful Lemmy mock server on a free port for real HTTP lifecycle testing."""
    server = socketserver.TCPServer(("127.0.0.1", 0), StatefulLemmyHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()
    server.server_close()

@pytest.mark.asyncio
async def test_lemmy_real_http_lifecycle(lemmy_test_server):
    """
    Integration Standard 1 & Must-have 8:
    Tests Lemmy connector against local HTTP integration test server with SIMULATION_MODE disabled.
    Strictly verifies full real HTTP lifecycle over TCP socket:
      1. publish -> real HTTP POST to /api/v3/post
      2. get_status -> real HTTP GET to /api/v3/post?id=... (verifies 'live')
      3. delete -> real HTTP POST to /api/v3/post/delete (verifies deleted=True)
      4. post-deletion verification -> real HTTP GET confirms status is 'deleted' (404)
    Fails immediately if any stage fails. Never falls back to validation.
    """
    connector = connector_registry.get("lemmy")
    dest = Destination(
        name="Local Real HTTP Lemmy Instance",
        url=lemmy_test_server,
        platform_key="lemmy",
        connector_key="lemmy",
        custom_params={"community_id": 1}
    )
    conn = Connection(base_url=lemmy_test_server, token="real_test_token_123")
    rendition = Rendition(
        title="Local Real HTTP Integration Probe",
        body="Testing real HTTP lifecycle over socket without simulation."
    )

    orig_mode = settings.SIMULATION_MODE
    settings.SIMULATION_MODE = False
    try:
        # 1. Real HTTP Publish
        pub = await connector.publish(rendition, dest, conn, "lemmy_real_http_key_01")
        assert pub.platform_post_id is not None
        assert pub.status == "published"
        assert lemmy_test_server in pub.live_url

        # 2. Real HTTP Status Probe (Must be confirmed live)
        st = await connector.get_status(pub.platform_post_id, conn)
        assert st.status == "live"
        assert st.live_url == f"{lemmy_test_server}/post/{pub.platform_post_id}"

        # 3. Real HTTP Deletion
        del_res = await connector.delete(pub.platform_post_id, conn)
        assert del_res.deleted is True

        # 4. Real HTTP Post-Deletion Verification (Must confirm deleted / 404)
        post_del_st = await connector.get_status(pub.platform_post_id, conn)
        assert post_del_st.status == "deleted"
    finally:
        settings.SIMULATION_MODE = orig_mode

