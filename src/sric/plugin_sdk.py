from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .models import ActionProposal
from .plugins import PluginManifest, PluginPermission, PluginRegistry


class PluginResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    proposed_actions: list[ActionProposal] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class PluginContext:
    workspace: Path
    granted_permissions: frozenset[PluginPermission]
    mode: str


class SRICPlugin(Protocol):
    def run(self, context: PluginContext, payload: dict[str, Any]) -> PluginResult: ...


class PluginBroker:
    """Mediates trusted in-process plugins without granting an executor.

    Plugins receive a narrow context and may only return observations/artifacts/action proposals.
    Any proposed active action must still pass Scope -> Policy -> Rate Limits -> Approval -> Executor.
    This broker is not an OS sandbox; untrusted plugin code must not be loaded in-process.
    """

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry

    def invoke_trusted(
        self,
        manifest: PluginManifest,
        plugin: SRICPlugin,
        *,
        workspace: Path,
        payload: dict[str, Any],
        required_permissions: set[PluginPermission] | None = None,
        mode: str = "PASSIVE",
    ) -> PluginResult:
        if self.registry.is_disabled(manifest.name):
            raise PermissionError(f"plugin {manifest.name} is disabled")
        required = required_permissions or set()
        for permission in required:
            self.registry.assert_permission(manifest, permission)
        context = PluginContext(
            workspace=workspace.resolve(),
            granted_permissions=frozenset(manifest.permissions),
            mode=mode,
        )
        result = plugin.run(context, payload)
        if not isinstance(result, PluginResult):
            raise TypeError("plugin must return PluginResult")
        # Active actions are proposals only. The broker intentionally exposes no executor object.
        return result
