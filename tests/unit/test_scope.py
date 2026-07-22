from sric.scope import ScopeEngine, ScopePolicy


def test_deny_precedence() -> None:
    e = ScopeEngine(
        ScopePolicy(allow_targets=["*.example.com"], deny_targets=["payments.example.com"])
    )
    assert e.evaluate("https://api.example.com", "GET").allowed
    d = e.evaluate("https://payments.example.com", "GET")
    assert not d.allowed and d.matched_rule == "targets.deny"


def test_method_denied() -> None:
    d = ScopeEngine(ScopePolicy(allow_targets=["example.com"])).evaluate(
        "https://example.com", "POST"
    )
    assert not d.allowed


def test_private_ip_blocked_unless_allowed() -> None:
    e = ScopeEngine(ScopePolicy(allow_targets=["example.com"]))
    assert not e.evaluate("https://example.com", "GET", resolved_ips=["127.0.0.1"]).allowed
    e2 = ScopeEngine(ScopePolicy(allow_targets=["example.com"], allow_networks=["127.0.0.0/8"]))
    assert e2.evaluate("https://example.com", "GET", resolved_ips=["127.0.0.1"]).allowed
