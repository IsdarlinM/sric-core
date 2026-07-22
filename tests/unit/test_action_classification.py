from sric.action_classification import classify_http_action
from sric.models import ActionClass


def test_delete_is_destructive_by_default() -> None:
    assert classify_http_action("DELETE", "https://example.com/resource/1") == ActionClass.MUTATING_DESTRUCTIVE


def test_get_is_not_automatically_safe() -> None:
    assert classify_http_action("GET", "https://example.com/logout") == ActionClass.MUTATING_REVERSIBLE
    assert classify_http_action("GET", "https://example.com/admin/export") == ActionClass.READ_ONLY_SENSITIVE


def test_plain_get_is_safe_baseline() -> None:
    assert classify_http_action("GET", "https://example.com/products") == ActionClass.READ_ONLY_SAFE
