from sric.redaction import redact_text


def test_secret_headers_redacted() -> None:
    raw = "Authorization: Bearer secret-token\nCookie: session=abc"
    result = redact_text(raw)
    assert "secret-token" not in result.text
    assert "session=abc" not in result.text
