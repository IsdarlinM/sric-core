from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class ContextTrust(StrEnum):
    SYSTEM_POLICY = "SYSTEM_POLICY"
    DEVELOPER_RULES = "DEVELOPER_RULES"
    USER_TASK = "USER_TASK"
    UNTRUSTED_EXTERNAL_DATA = "UNTRUSTED_EXTERNAL_DATA"


@dataclass(frozen=True)
class LabeledContext:
    trust: ContextTrust
    content: str
    source: str = "unspecified"
    indicators: list[str] = field(default_factory=list)


_INJECTION_HINTS = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"reveal\s+(the\s+)?(system|developer)\s+prompt", re.I),
    re.compile(r"export\s+.*(api[_ -]?key|token|secret|password)", re.I),
    re.compile(r"disable\s+.*(policy|safety|scope)", re.I),
)


class PromptBoundary:
    """Labels target content as data and surfaces injection indicators without obeying it."""

    @staticmethod
    def indicators(content: str) -> list[str]:
        found: list[str] = []
        for pattern in _INJECTION_HINTS:
            if pattern.search(content):
                found.append(pattern.pattern)
        return found

    @classmethod
    def external_data(cls, content: str) -> LabeledContext:
        return cls.label_external(content)

    @classmethod
    def label_external(cls, content: str, source: str = "external") -> LabeledContext:
        return LabeledContext(
            ContextTrust.UNTRUSTED_EXTERNAL_DATA,
            content,
            source=source,
            indicators=cls.indicators(content),
        )

    @staticmethod
    def render_for_model(
        contexts: list[LabeledContext],
        *,
        system_policy: str | None = None,
        user_task: str | None = None,
    ) -> str:
        chunks: list[str] = []
        if system_policy is not None:
            chunks.append(f'<context trust="{ContextTrust.SYSTEM_POLICY}">\n{system_policy}\n</context>')
        if user_task is not None:
            chunks.append(f'<context trust="{ContextTrust.USER_TASK}">\n{user_task}\n</context>')
        for ctx in contexts:
            chunks.append(
                f'<context trust="{ctx.trust}" source="{ctx.source}">\n{ctx.content}\n</context>'
            )
        return "\n".join(chunks)
