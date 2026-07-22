from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from ipaddress import ip_address
from typing import Any

from .ai import AIProvider, AIRequest, AIResponse, AIService, AIBudget, DisabledAIProvider

MAX_AI_RESPONSE_BYTES = 5 * 1024 * 1024


class AIProviderMode(StrEnum):
    DISABLED = "disabled"
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise urllib.error.HTTPError(req.full_url, code, "AI provider redirects are disabled", headers, fp)


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _validate_endpoint(url: str, *, external: bool) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.username or parsed.password:
        raise ValueError("AI endpoint URL must not embed credentials")
    if external:
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("external AI endpoints require HTTPS")
    else:
        if parsed.scheme not in {"http", "https"} or not _is_loopback_host(parsed.hostname):
            raise ValueError("local AI endpoints must resolve by configuration to loopback hostnames/IPs")


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        data = response.read(MAX_AI_RESPONSE_BYTES + 1)
    if len(data) > MAX_AI_RESPONSE_BYTES:
        raise ValueError("AI provider response exceeds size limit")
    decoded = json.loads(data)
    if not isinstance(decoded, dict):
        raise ValueError("AI provider response must be a JSON object")
    return decoded


@dataclass
class OpenAICompatibleProvider(AIProvider):
    endpoint: str
    model: str
    api_key: str | None = None
    external: bool = True
    timeout: float = 30.0
    name: str = "openai-compatible"

    def __post_init__(self) -> None:
        _validate_endpoint(self.endpoint, external=self.external)

    def complete(self, request: AIRequest) -> AIResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.sanitized_payload}],
            "max_tokens": request.max_tokens,
        }
        data = _post_json(self.endpoint, payload, headers, self.timeout)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("AI provider response missing choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str):
            raise ValueError("AI provider response missing message content")
        return AIResponse(text=text, provider=self.name, model=self.model)


@dataclass
class OllamaProvider(AIProvider):
    base_url: str
    model: str
    timeout: float = 60.0
    name: str = "ollama"
    external: bool = False

    def __post_init__(self) -> None:
        _validate_endpoint(self.base_url, external=False)

    def complete(self, request: AIRequest) -> AIResponse:
        endpoint = self.base_url.rstrip("/") + "/api/generate"
        data = _post_json(
            endpoint,
            {"model": self.model, "prompt": request.sanitized_payload, "stream": False},
            {},
            self.timeout,
        )
        text = data.get("response")
        if not isinstance(text, str):
            raise ValueError("Ollama response missing text")
        return AIResponse(text=text, provider=self.name, model=self.model)


@dataclass
class HybridAIService:
    """Capability router with explicit local/cloud services; defaults to disabled."""

    local: AIService = field(default_factory=lambda: AIService(DisabledAIProvider(), AIBudget()))
    cloud: AIService = field(default_factory=lambda: AIService(DisabledAIProvider(), AIBudget()))
    capability_routes: dict[str, AIProviderMode] = field(default_factory=dict)

    def preview(self, request: AIRequest) -> Any:
        mode = self.capability_routes.get(request.capability, AIProviderMode.DISABLED)
        if mode == AIProviderMode.LOCAL:
            return self.local.preview(request)
        if mode == AIProviderMode.CLOUD:
            return self.cloud.preview(request)
        raise PermissionError(f"AI capability is not explicitly routed: {request.capability}")

    def complete(self, request: AIRequest, *, approved_external_ai: bool = False) -> AIResponse:
        mode = self.capability_routes.get(request.capability, AIProviderMode.DISABLED)
        if mode == AIProviderMode.LOCAL:
            return self.local.complete(request, approved=True)
        if mode == AIProviderMode.CLOUD:
            return self.cloud.complete(request, approved=approved_external_ai)
        raise PermissionError(f"AI capability is disabled or unsupported in route: {request.capability}")
