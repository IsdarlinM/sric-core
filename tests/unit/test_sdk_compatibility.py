import pytest

from sric.sdk import (
    CompatibilityStatus,
    SDKManifest,
    check_sdk_compatibility,
)


def manifest() -> SDKManifest:
    return SDKManifest(
        sdk_name="collector-sdk",
        sdk_version="1.0.0",
        minimum_core_version="0.4.1",
        maximum_core_version_exclusive="0.5.0",
        plugin_types=["collector"],
        required_permissions=["network:read"],
        supported_schema_versions={"evidence": ["2.0"]},
        deprecated_features=["legacy-import"],
        migration_notes=["Replace legacy-import with hostile-import-preflight."],
    )


def test_compatible_sdk_contract() -> None:
    report = check_sdk_compatibility(
        manifest(),
        core_version="0.4.1",
        available_plugin_types=["collector"],
        granted_permissions=["network:read"],
        available_schema_versions={"evidence": "2.0"},
    )

    assert report.compatible is True
    assert report.status is CompatibilityStatus.COMPATIBLE
    assert report.reasons == []


def test_core_version_window_fails_closed() -> None:
    report = check_sdk_compatibility(
        manifest(),
        core_version="0.5.0",
        available_plugin_types=["collector"],
        granted_permissions=["network:read"],
        available_schema_versions={"evidence": "2.0"},
    )

    assert report.compatible is False
    assert report.status is CompatibilityStatus.INCOMPATIBLE
    assert "outside the supported window" in report.reasons[0]


def test_missing_permission_and_schema_are_reported() -> None:
    report = check_sdk_compatibility(
        manifest(),
        core_version="0.4.1",
        available_plugin_types=["collector"],
        granted_permissions=[],
        available_schema_versions={"evidence": "1.0"},
    )

    assert report.missing_permissions == ["network:read"]
    assert report.unsupported_schemas == {"evidence": ["2.0"]}
    assert report.compatible is False


def test_deprecated_feature_does_not_hide_compatibility() -> None:
    report = check_sdk_compatibility(
        manifest(),
        core_version="0.4.1",
        available_plugin_types=["collector"],
        granted_permissions=["network:read"],
        available_schema_versions={"evidence": "2.0"},
        enabled_features=["legacy-import"],
    )

    assert report.compatible is True
    assert report.status is CompatibilityStatus.DEPRECATED
    assert report.migration_notes


def test_invalid_manifest_version_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="must exceed"):
        SDKManifest(
            sdk_name="invalid",
            sdk_version="1.0.0",
            minimum_core_version="0.5.0",
            maximum_core_version_exclusive="0.5.0",
        )
