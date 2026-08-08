from sric.capabilities import discover_capabilities, integration_available


def test_incompatible_installed_product_does_not_publish_capabilities() -> None:
    versions = {
        "sric-core": "0.5.0",
        "fossilscope": "0.5.0",
        "exposuredna": "0.4.9",
    }
    report = discover_capabilities(
        current_product="fossilscope",
        version_resolver=lambda name: versions.get(name),
    )
    exposure = next(item for item in report.products if item.product == "exposuredna")
    assert exposure.installed is True
    assert exposure.compatible is False
    assert exposure.capabilities == []
    assert integration_available("organization.resolution", report) is False


def test_incompatible_core_makes_product_not_ready() -> None:
    versions = {"sric-core": "0.6.0", "fossilscope": "0.5.0"}
    report = discover_capabilities(
        current_product="fossilscope",
        version_resolver=lambda name: versions.get(name),
    )
    assert report.core_compatible is False
    assert report.standalone_ready is False
    assert report.available_capabilities == []
