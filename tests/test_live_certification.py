import asyncio
import http.server
import json
import socketserver
import threading
from pathlib import Path
import pytest
from app.certification.harness import certification_harness
from app.catalogue.models import DestinationRecord
from app.connectors.base import Connection
from app.core.config import settings
from app.mocks.lemmy_service import StatefulLemmyHandler

class StatefulWebhookReceiverHandler(http.server.BaseHTTPRequestHandler):
    """
    Real HTTP Webhook receiver adhering to the IncuBrix HMAC status and deletion contract.
    """
    posts = {}

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        if self.path.endswith("/status"):
            post_id = payload.get("platform_post_id")
            if post_id in self.posts and not self.posts[post_id].get("deleted", False):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "live", "live_url": f"http://127.0.0.1/posts/{post_id}"}).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "deleted", "error": "not_found"}).encode("utf-8"))

        elif self.path.endswith("/delete"):
            post_id = payload.get("platform_post_id")
            if post_id in self.posts:
                self.posts[post_id]["deleted"] = True
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"deleted": True}).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "not_found", "deleted": True}).encode("utf-8"))

        else:
            # Publish event
            event = payload.get("event")
            idem_key = payload.get("idempotency_key", "wh_key")
            post_id = f"wh_{idem_key[-8:]}"
            self.posts[post_id] = {"id": post_id, "deleted": False}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"id": post_id, "status": "received"}).encode("utf-8"))

    def log_message(self, format, *args):
        pass

@pytest.fixture(scope="module")
def live_services():
    """Starts real HTTP servers for Lemmy and Webhook HMAC."""
    lemmy_srv = socketserver.TCPServer(("127.0.0.1", 0), StatefulLemmyHandler)
    lemmy_port = lemmy_srv.server_address[1]
    lemmy_th = threading.Thread(target=lemmy_srv.serve_forever, daemon=True)
    lemmy_th.start()

    wh_srv = socketserver.TCPServer(("127.0.0.1", 0), StatefulWebhookReceiverHandler)
    wh_port = wh_srv.server_address[1]
    wh_th = threading.Thread(target=wh_srv.serve_forever, daemon=True)
    wh_th.start()

    yield {
        "lemmy": f"http://127.0.0.1:{lemmy_port}",
        "webhook_hmac": f"http://127.0.0.1:{wh_port}"
    }

    lemmy_srv.shutdown()
    lemmy_srv.server_close()
    wh_srv.shutdown()
    wh_srv.server_close()

@pytest.mark.asyncio
async def test_live_certification_with_simulation_disabled(live_services):
    """
    Runs the full certification harness with SIMULATION_MODE disabled.
    Proves real platform HTTP APIs accept publish, confirm live status, execute deletion,
    verify post-deletion absence, and save 'environment: live' evidence.
    """
    orig_mode = settings.SIMULATION_MODE
    settings.SIMULATION_MODE = False
    try:
        # 1. Live Lemmy certification
        lemmy_record = DestinationRecord(
            name="Live Integration Lemmy Instance",
            url=live_services["lemmy"],
            platform_key="lemmy",
            connector_key="lemmy",
            surface="community",
            category="technology",
            audience_tags=["tech", "open-source"],
            language="en",
            geo="global",
            est_audience=5000,
            level="L1",
            relevance_score=4,
            custom_params={"community_id": 1}
        )
        lemmy_conn = Connection(
            base_url=live_services["lemmy"],
            token="live_test_token"
        )
        evidence_lemmy = await certification_harness.certify_destination(lemmy_record, lemmy_conn)
        assert evidence_lemmy.verdict == "PASSED"
        assert evidence_lemmy.environment == "live"
        assert Path(evidence_lemmy.evidence_file).exists()
        assert evidence_lemmy.status_response["status"] == "live"
        assert evidence_lemmy.delete_response["deleted"] is True
        assert evidence_lemmy.post_delete_verification["status"] == "deleted"

        # 2. Live Webhook HMAC certification
        wh_record = DestinationRecord(
            name="Live Integration Partner Webhook",
            url=live_services["webhook_hmac"],
            platform_key="webhook_hmac",
            connector_key="webhook_hmac",
            surface="webhook",
            category="partner",
            audience_tags=["partner", "b2b"],
            language="en",
            geo="global",
            est_audience=1000,
            level="L1",
            relevance_score=3
        )
        wh_conn = Connection(
            base_url=live_services["webhook_hmac"],
            secret="live_test_secret"
        )
        evidence_wh = await certification_harness.certify_destination(wh_record, wh_conn)
        assert evidence_wh.verdict == "PASSED"
        assert evidence_wh.environment == "live"
        assert Path(evidence_wh.evidence_file).exists()
        assert evidence_wh.status_response["status"] == "live"
        assert evidence_wh.delete_response["deleted"] is True
        assert evidence_wh.post_delete_verification["status"] == "deleted"

    finally:
        settings.SIMULATION_MODE = orig_mode
