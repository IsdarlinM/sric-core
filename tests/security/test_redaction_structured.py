from sric.redaction import redact_body, redact_url


def test_redact_sensitive_query_parameters() -> None:
    result = redact_url("https://example.com/cb?access_token=SECRET&code=ABC&x=1")
    assert "SECRET" not in result.text
    assert "ABC" in result.text
    assert result.detected["access_token"] == 1


def test_redact_json_secrets_recursively() -> None:
    result = redact_body(
        '{"password":"SECRET","nested":{"client_secret":"XYZ"},"safe":"ok"}',
        "application/json",
    )
    assert '"password":"SECRET"' not in result.text
    assert '"client_secret":"XYZ"' not in result.text
    assert '"safe":"ok"' in result.text
    assert result.detected["password"] == 1
    assert result.detected["client_secret"] == 1


def test_redact_urlencoded_body() -> None:
    result = redact_body("username=a&password=secret", "application/x-www-form-urlencoded")
    assert "secret" not in result.text
    assert result.detected["password"] == 1


def test_audit_logger_redacts_query_secrets(tmp_path) -> None:
    import json
    from sric.audit import AuditLogger

    path = tmp_path / "audit.jsonl"
    AuditLogger(path).write(
        user="u",
        action="GET",
        target="https://example.com/cb?access_token=TOPSECRET",
        policy_decision="allow",
        result="ok",
        tool_version="0.2.0",
    )
    event = json.loads(path.read_text())
    assert "TOPSECRET" not in event["target"]
    assert "REDACTED_ACCESS_TOKEN" in event["target"]
