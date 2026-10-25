"""
Stateful Lemmy API Mock Server
Implements realistic Lemmy v3 HTTP endpoints:
  - POST /api/v3/post: Creates and stores a post by ID
  - GET /api/v3/post?id={id}: Returns 200 with post_view if live, 404 if deleted/not_found
  - POST /api/v3/post/delete: Marks post as deleted
"""
import http.server
import json
import socketserver
import urllib.parse
from typing import Dict, Any

posts: Dict[str, Dict[str, Any]] = {}
post_counter = 100

class StatefulLemmyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        global post_counter
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {}

        if parsed.path.endswith("/api/v3/post/delete"):
            post_id = str(data.get("post_id", ""))
            if post_id in posts:
                posts[post_id]["deleted"] = True
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "post_view": {
                        "post": {
                            "id": int(post_id) if post_id.isdigit() else 1,
                            "deleted": True
                        }
                    }
                }).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "post_not_found"}).encode("utf-8"))

        elif parsed.path.endswith("/api/v3/post"):
            post_counter += 1
            post_id = str(post_counter)
            name = data.get("name", "Untitled Lemmy Post")
            body_text = data.get("body", "")
            posts[post_id] = {
                "id": int(post_id),
                "name": name,
                "body": body_text,
                "deleted": False
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "post_view": {
                    "post": {
                        "id": int(post_id),
                        "name": name,
                        "deleted": False
                    }
                }
            }).encode("utf-8"))

        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
            return

        query = urllib.parse.parse_qs(parsed.query)
        post_id = str(query.get("id", [""])[0])
        if post_id in posts and not posts[post_id].get("deleted", False):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "live",
                "post_view": {
                    "post": posts[post_id]
                }
            }).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "deleted",
                "error": "not_found"
            }).encode("utf-8"))

    def log_message(self, format, *args):
        pass

def run_server(port: int = 8536):
    with socketserver.TCPServer(("0.0.0.0", port), StatefulLemmyHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
