"""Exercise real PyGithub serialization and readback over a bounded local HTTP server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from github import Github, GithubException

import storygraph_box as box


@pytest.fixture
def transport(monkeypatch):
    state = {"content": "before", "requests": [], "mismatch": False, "fail": ""}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, code, data):
            payload = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def handle_gist(self, method):
            assert self.path == "/gists/transport-test"
            state["requests"].append(method)
            if state["fail"] == method:
                self.respond(401, {"message": "Bad credentials"})
                return
            if method == "PATCH":
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert set(data["files"]) == {"latest reads"}
                if not state["mismatch"]:
                    state["content"] = data["files"]["latest reads"]["content"]
            self.respond(200, {
                "id": "transport-test",
                "files": {"latest reads": {"filename": "latest reads", "content": state["content"]}},
            })

        def do_GET(self):
            self.handle_gist("GET")

        def do_PATCH(self):
            self.handle_gist("PATCH")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setattr(box, "GH_TOKEN", "fictional-local-test-token")
    monkeypatch.setattr(box, "GIST_ID", "transport-test")
    monkeypatch.setattr(box, "Github", lambda **kwargs: Github(
        **kwargs, base_url=f"http://127.0.0.1:{server.server_port}", timeout=3, retry=0
    ))
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def test_real_library_writes_unicode_and_verifies_it(transport):
    body = "🎧 Audio: Şocul întoarcerii în ţară by Neagu Djuvara\n📅 2026: 0/5 books"
    box.update_gist(body)
    assert transport["content"] == body
    assert transport["requests"] == ["GET", "PATCH", "GET"]


def test_real_library_skips_identical_content(transport):
    box.update_gist("before")
    assert transport["requests"] == ["GET"]


def test_real_library_rejects_wrong_readback_without_retry(transport):
    transport["mismatch"] = True
    with pytest.raises(RuntimeError, match="readback"):
        box.update_gist("changed")
    assert transport["requests"] == ["GET", "PATCH", "GET"]


@pytest.mark.parametrize("method,requests", [("GET", ["GET"]), ("PATCH", ["GET", "PATCH"])])
def test_http_failure_is_fatal_and_never_retried(transport, method, requests):
    transport["fail"] = method
    with pytest.raises(GithubException):
        box.update_gist("changed")
    assert transport["requests"] == requests
