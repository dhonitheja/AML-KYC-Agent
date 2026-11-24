"""Shared test guards and helpers (PLAN-002 T1; loopback fake model server for T3/T5)."""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

try:
    import anthropic
except ImportError:  # stub-only installs never load the SDK
    anthropic = None

MODEL_ENV = ("ANTHROPIC_API_KEY", "LLM_MODE", "DATA_CLASSIFICATION", "LOCAL_LLM_URL", "LLM_MODEL")


class _NoNetworkClient:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("tests must not construct a network model client")


# FR-010.2 AC-2 / NFR-008 AC-3 (support): no test sees a model env var or can build a real Anthropic client.
@pytest.fixture(autouse=True)
def no_model_network(monkeypatch):
    for name in MODEL_ENV:
        monkeypatch.delenv(name, raising=False)
    if anthropic is not None:
        monkeypatch.setattr(anthropic, "Anthropic", _NoNetworkClient)


def free_port():
    """A loopback port with nothing listening (bind, read the port, close)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeModelServer:
    """Ollama-shaped server on 127.0.0.1:0 in a daemon thread. Only loopback targets are allowed (T1).

    `responder(request) -> (status, headers, body)` is called per request; `request` is a dict with
    method, path, headers (lower-cased names) and the raw body. Every request is recorded in `requests`."""

    def __init__(self, responder):
        self.requests = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                req = dict(method=self.command, path=self.path, body=body,
                           headers={k.lower(): v for k, v in self.headers.items()})
                server.requests.append(req)
                status, headers, payload = responder(req)
                if isinstance(payload, (dict, list)):
                    payload = json.dumps(payload)
                if isinstance(payload, str):
                    payload = payload.encode()
                try:
                    self.send_response(status)
                    for k, v in (headers or {}).items():
                        self.send_header(k, v)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except OSError:  # client gave up (timeout tests)
                    pass

            do_POST = do_GET = _serve

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.httpd.handle_error = lambda *a: None
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, args=(0.05,), daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def fake_server():
    """Factory: fake_server(responder) -> started FakeModelServer, shut down after the test."""
    started = []

    def start(responder):
        started.append(FakeModelServer(responder))
        return started[-1]

    yield start
    for s in started:
        s.close()


def chat_reply(content, model="server-echo-model", done_reason="stop", **extra):
    """A 200 /api/chat body in the DI-011 shape."""
    return 200, {"Content-Type": "application/json"}, dict(
        model=model, message={"role": "assistant", "content": content}, done=True, done_reason=done_reason, **extra)


def stub_replying_server(fake_server):
    """A loopback server answering every /api/chat with StubLLM's JSON for the same system/user prompt."""
    from llm import StubLLM

    def responder(req):
        msgs = json.loads(req["body"])["messages"]
        system = next(m["content"] for m in msgs if m["role"] == "system")
        user = next(m["content"] for m in msgs if m["role"] == "user")
        return chat_reply(StubLLM().complete(system, user)[0])

    return fake_server(responder)


class Sleeps(list):
    """Injected sleep for complete_with_retry: records requested backoffs, never sleeps."""

    def __call__(self, seconds):
        self.append(seconds)

