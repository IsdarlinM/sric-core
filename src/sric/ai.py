from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AIRequest:
    capability: str
    sanitized_payload: str
    max_tokens: int = 1024


@dataclass(frozen=True)
class AIResponse:
    text: str
    provider: str
    model: str


@dataclass(frozen=True)
class AIPrivacyPreview:
    provider: str
    capability: str
    characters: int
    estimated_tokens: int
    max_output_tokens: int
    external_send: bool
    note: str


@dataclass
class AIBudget:
    max_calls: int = 0
    max_estimated_tokens: int = 0
    calls_used: int = 0
    estimated_tokens_used: int = 0

    def authorize(self, estimated_tokens: int) -> None:
        if self.max_calls <= 0 or self.max_estimated_tokens <= 0:
            raise PermissionError("AI budget is disabled; configure explicit positive limits")
        if self.calls_used + 1 > self.max_calls:
            raise PermissionError("AI call budget exceeded")
        if self.estimated_tokens_used + estimated_tokens > self.max_estimated_tokens:
            raise PermissionError("AI token budget exceeded")

    def consume(self, estimated_tokens: int) -> None:
        self.calls_used += 1
        self.estimated_tokens_used += estimated_tokens


class AIProvider(Protocol):
    name: str
    model: str
    external: bool

    def complete(self, request: AIRequest) -> AIResponse: ...


class DisabledAIProvider:
    name = "disabled"
    model = "none"
    external = False

    def complete(self, request: AIRequest) -> AIResponse:
        raise RuntimeError("AI is disabled. Core functionality remains available without AI.")


@dataclass
class AIService:
    provider: AIProvider = field(default_factory=DisabledAIProvider)
    budget: AIBudget = field(default_factory=AIBudget)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Deliberately conservative provider-neutral estimate; not presented as billing truth.
        return max(1, (len(text) + 2) // 3)

    def preview(self, request: AIRequest) -> AIPrivacyPreview:
        estimate = self._estimate_tokens(request.sanitized_payload) + request.max_tokens
        return AIPrivacyPreview(
            provider=self.provider.name,
            capability=request.capability,
            characters=len(request.sanitized_payload),
            estimated_tokens=estimate,
            max_output_tokens=request.max_tokens,
            external_send=self.provider.external,
            note="Payload must already be sanitized; preview never transmits data.",
        )

    def complete(self, request: AIRequest, *, approved: bool = False) -> AIResponse:
        preview = self.preview(request)
        self.budget.authorize(preview.estimated_tokens)
        if self.provider.external and not approved:
            raise PermissionError("external AI send requires explicit approval after privacy preview")
        response = self.provider.complete(request)
        self.budget.consume(preview.estimated_tokens)
        return response
