import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from sric.ai import AIBudget, AIRequest, AIService
from sric.ai_providers import AIProviderMode, HybridAIService, OpenAICompatibleProvider


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps({"choices": [{"message": {"content": "local result"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass


def test_openai_compatible_local_adapter_and_hybrid_route():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = OpenAICompatibleProvider(
            endpoint=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            model="local-model",
            external=False,
        )
        local = AIService(provider, AIBudget(max_calls=1, max_estimated_tokens=5000))
        hybrid = HybridAIService(local=local, capability_routes={"summarize": AIProviderMode.LOCAL})
        result = hybrid.complete(AIRequest("summarize", "sanitized"))
        assert result.text == "local result"
    finally:
        server.shutdown()
        thread.join()


def test_external_provider_rejects_insecure_http():
    try:
        OpenAICompatibleProvider(endpoint="http://example.com/v1/chat/completions", model="x", external=True)
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("external provider must require HTTPS")
