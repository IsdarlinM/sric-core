from __future__ import annotations

from sric.capabilities import discover_capabilities, integration_available


def test_product_absence_is_optional_not_error() -> None:
    versions = {"sric-core": "0.5.0", "fossilscope": "0.5.0"}
    report = discover_capabilities(
        current_product="fossilscope",
        version_resolver=lambda name: versions.get(name),
    )
    assert report.standalone_ready is True
    assert "temporal.archaeology" in report.available_capabilities
    assert integration_available("organization.resolution", report) is False
    assert next(item for item in report.products if item.product == "exposuredna").installed is False


def test_optional_product_appears_without_changing_core_contract() -> None:
    versions = {
        "sric-core": "0.5.0",
        "fossilscope": "0.5.0",
        "exposuredna": "0.5.0",
    }
    report = discover_capabilities(
        current_product="fossilscope",
        version_resolver=lambda name: versions.get(name),
    )
    assert report.standalone_ready is True
    assert integration_available("organization.resolution", report) is True


def test_missing_current_product_is_not_standalone_ready() -> None:
    report = discover_capabilities(
        current_product="fossilscope",
        version_resolver=lambda name: "0.5.0" if name == "sric-core" else None,
    )
    assert report.standalone_ready is False
