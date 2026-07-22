from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PluginType(StrEnum):
    COLLECTOR = "collector"
    IMPORTER = "importer"
    EXPORTER = "exporter"
    ANALYZER = "analyzer"
    VALIDATOR = "validator"
    AI_PROVIDER = "ai_provider"
    REPORTER = "reporter"
    VISUALIZER = "visualizer"
    INTEGRATION = "integration"


class PluginPermission(StrEnum):
    NETWORK = "network"
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    SECRETS = "secrets"
    AI = "ai"
    ACTIVE_REQUESTS = "active_requests"


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    version: str
    api_version: str = "1"
    type: PluginType
    permissions: set[PluginPermission] = Field(default_factory=set)
    capabilities: list[str] = Field(default_factory=list)
    entrypoint: str


class PluginRegistry:
    """Manifest registry with fail-closed permission and enable/disable state.

    This registry does not auto-import or execute plugin Python code. Execution must be mediated by a
    product-specific runtime that re-checks permissions, scope, policy and approvals.
    """

    def __init__(self, manifests_dir: Path) -> None:
        self.manifests_dir = manifests_dir
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.disabled_dir = self.manifests_dir / ".disabled"
        self.disabled_dir.mkdir(exist_ok=True)

    def list(self, *, include_disabled: bool = True) -> list[PluginManifest]:
        manifests: list[PluginManifest] = []
        for path in sorted(self.manifests_dir.glob("*.json")):
            manifest = PluginManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if not include_disabled and self.is_disabled(manifest.name):
                continue
            manifests.append(manifest)
        return manifests

    def inspect(self, name: str) -> PluginManifest:
        matches = [m for m in self.list() if m.name == name]
        if not matches:
            raise KeyError(name)
        return matches[0]

    def install_manifest(self, source: Path) -> PluginManifest:
        if not source.is_file() or source.is_symlink():
            raise ValueError("plugin manifest must be a regular non-symlink file")
        if source.stat().st_size > 1024 * 1024:
            raise ValueError("plugin manifest exceeds 1 MiB limit")
        manifest = PluginManifest.model_validate(json.loads(source.read_text(encoding="utf-8")))
        target = self.manifests_dir / f"{manifest.name}.json"
        if target.exists():
            raise FileExistsError(f"plugin already installed: {manifest.name}")
        target.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest

    def remove(self, name: str) -> None:
        path = self.manifests_dir / f"{name}.json"
        if not path.is_file():
            raise KeyError(name)
        path.unlink()
        disabled = self.disabled_dir / name
        if disabled.exists():
            disabled.unlink()

    def disable(self, name: str) -> None:
        self.inspect(name)
        (self.disabled_dir / name).write_text("disabled\n", encoding="utf-8")

    def enable(self, name: str) -> None:
        self.inspect(name)
        marker = self.disabled_dir / name
        if marker.exists():
            marker.unlink()

    def is_disabled(self, name: str) -> bool:
        return (self.disabled_dir / name).exists()

    def verify(self, name: str) -> dict[str, object]:
        manifest = self.inspect(name)
        path = self.manifests_dir / f"{name}.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "name": manifest.name,
            "version": manifest.version,
            "api_version": manifest.api_version,
            "sha256": digest,
            "disabled": self.is_disabled(name),
            "permissions": sorted(x.value for x in manifest.permissions),
            "valid": True,
        }

    def assert_permission(self, manifest: PluginManifest, permission: PluginPermission) -> None:
        if self.is_disabled(manifest.name):
            raise PermissionError(f"plugin {manifest.name} is disabled")
        if permission not in manifest.permissions:
            raise PermissionError(f"plugin {manifest.name} lacks declared permission: {permission}")
