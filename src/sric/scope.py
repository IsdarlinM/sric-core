from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(slots=True)
class ScopePolicy:
    allow_targets: list[str] = field(default_factory=list)
    deny_targets: list[str] = field(default_factory=list)
    allow_networks: list[str] = field(default_factory=list)
    deny_networks: list[str] = field(default_factory=list)
    allowed_methods: set[str] = field(default_factory=lambda: {"GET", "HEAD", "OPTIONS"})
    enforce_redirect_scope: bool = True
    block_private_networks_unless_allowed: bool = True


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    allowed: bool
    reason: str
    matched_rule: str


class ScopeEngine:
    def __init__(self, policy: ScopePolicy) -> None:
        self.policy = policy

    @staticmethod
    def _host(target: str) -> str:
        parsed = urlsplit(target if "://" in target else f"https://{target}")
        if not parsed.hostname:
            raise ValueError("target must include a valid hostname")
        return parsed.hostname.rstrip(".").lower()

    def evaluate(
        self, target: str, method: str, *, resolved_ips: list[str] | None = None
    ) -> ScopeDecision:
        host = self._host(target)
        method = method.upper()
        if method not in self.policy.allowed_methods:
            return ScopeDecision(False, f"method {method} not allowed", "methods.default")
        if any(fnmatch.fnmatch(host, pat.lower()) for pat in self.policy.deny_targets):
            return ScopeDecision(False, "target explicitly denied", "targets.deny")
        if self.policy.allow_targets and not any(
            fnmatch.fnmatch(host, pat.lower()) for pat in self.policy.allow_targets
        ):
            return ScopeDecision(False, "target not present in allowlist", "targets.allow")
        for raw_ip in resolved_ips or []:
            ip = ipaddress.ip_address(raw_ip)
            if any(ip in ipaddress.ip_network(n, strict=False) for n in self.policy.deny_networks):
                return ScopeDecision(False, "resolved IP falls in denied network", "networks.deny")
            explicitly_allowed = any(
                ip in ipaddress.ip_network(n, strict=False) for n in self.policy.allow_networks
            )
            if (
                self.policy.block_private_networks_unless_allowed
                and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
                and not explicitly_allowed
            ):
                return ScopeDecision(
                    False, "private/special network not explicitly allowed", "ssrf.guard"
                )
        return ScopeDecision(True, "scope policy allows action", "allow")

    def evaluate_redirect(self, from_url: str, to_url: str, method: str) -> ScopeDecision:
        if not self.policy.enforce_redirect_scope:
            return ScopeDecision(
                True, "redirect revalidation disabled", "redirects.enforce_scope=false"
            )
        return self.evaluate(to_url, method)
