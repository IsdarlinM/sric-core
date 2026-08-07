from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    DEPRECATED = "DEPRECATED"
    UNKNOWN = "UNKNOWN"


class SDKManifest(BaseModel):
    """Versioned public SDK contract declared by a plugin or integration."""

    model_config = ConfigDict(extra="forbid")

    sdk_name: str
    sdk_version: str
    minimum_core_version: str
    maximum_core_version_exclusive: str
    plugin_types: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    supported_schema_versions: dict[str, list[str]] = Field(default_factory=dict)
    deprecated_features: list[str] = Field(default_factory=list)
    migration_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def version_window(self) -> "SDKManifest":
        minimum = semantic_version(self.minimum_core_version)
        maximum = semantic_version(self.maximum_core_version_exclusive)
        semantic_version(self.sdk_version)
        if maximum <= minimum:
            raise ValueError("maximum_core_version_exclusive must exceed minimum_core_version")
        return self


class SDKCompatibilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sdk_name: str
    sdk_version: str
    core_version: str
    status: CompatibilityStatus
    compatible: bool
    missing_plugin_types: list[str] = Field(default_factory=list)
    missing_permissions: list[str] = Field(default_factory=list)
    unsupported_schemas: dict[str, list[str]] = Field(default_factory=dict)
    deprecated_features: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    migration_notes: list[str] = Field(default_factory=list)


def semantic_version(value: str) -> tuple[int, int, int]:
    core = value.split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"unsupported semantic version: {value}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def check_sdk_compatibility(
    manifest: SDKManifest,
    *,
    core_version: str,
    available_plugin_types: Iterable[str] = (),
    granted_permissions: Iterable[str] = (),
    available_schema_versions: dict[str, str] | None = None,
    enabled_features: Iterable[str] = (),
) -> SDKCompatibilityReport:
    current = semantic_version(core_version)
    minimum = semantic_version(manifest.minimum_core_version)
    maximum = semantic_version(manifest.maximum_core_version_exclusive)
    types = set(available_plugin_types)
    permissions = set(granted_permissions)
    schemas = available_schema_versions or {}
    features = set(enabled_features)

    reasons: list[str] = []
    if current < minimum:
        reasons.append(
            f"Core {core_version} is older than required {manifest.minimum_core_version}."
        )
    if current >= maximum:
        reasons.append(
            f"Core {core_version} is outside the supported window ending before "
            f"{manifest.maximum_core_version_exclusive}."
        )

    missing_types = sorted(set(manifest.plugin_types) - types)
    if missing_types:
        reasons.append("Required plugin types are unavailable.")
    missing_permissions = sorted(set(manifest.required_permissions) - permissions)
    if missing_permissions:
        reasons.append("Required permissions were not granted.")

    unsupported: dict[str, list[str]] = {}
    for schema, supported in manifest.supported_schema_versions.items():
        available = schemas.get(schema)
        if available is None or available not in supported:
            unsupported[schema] = list(supported)
    if unsupported:
        reasons.append("One or more schema versions are unsupported.")

    deprecated = sorted(features & set(manifest.deprecated_features))
    compatible = not reasons
    if not compatible:
        status = CompatibilityStatus.INCOMPATIBLE
    elif deprecated:
        status = CompatibilityStatus.DEPRECATED
    else:
        status = CompatibilityStatus.COMPATIBLE

    return SDKCompatibilityReport(
        sdk_name=manifest.sdk_name,
        sdk_version=manifest.sdk_version,
        core_version=core_version,
        status=status,
        compatible=compatible,
        missing_plugin_types=missing_types,
        missing_permissions=missing_permissions,
        unsupported_schemas=unsupported,
        deprecated_features=deprecated,
        reasons=reasons,
        migration_notes=manifest.migration_notes,
    )
