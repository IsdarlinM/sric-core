from __future__ import annotations

import json
import os
import subprocess
import sys
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
    """Trusted in-process broker. No executor object is exposed to plugins."""

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry

    def invoke_trusted(self, manifest: PluginManifest, plugin: SRICPlugin, *, workspace: Path, payload: dict[str, Any], required_permissions: set[PluginPermission] | None = None, mode: str = "PASSIVE") -> PluginResult:
        if self.registry.is_disabled(manifest.name):
            raise PermissionError(f"plugin {manifest.name} is disabled")
        for permission in required_permissions or set():
            self.registry.assert_permission(manifest, permission)
        context = PluginContext(workspace.resolve(), frozenset(manifest.permissions), mode)
        result = plugin.run(context, payload)
        if not isinstance(result, PluginResult):
            raise TypeError("plugin must return PluginResult")
        return result


class IsolatedPluginRunner:
    """Runs a trusted adapter in a child process using a narrow JSON contract.

    This provides process isolation and resource limits where supported. It is not claimed to be a
    hostile-code OS sandbox. The child never receives an executor, policy bypass, or raw secret store.
    """

    def __init__(self, registry: PluginRegistry, *, timeout_seconds: float = 30.0, memory_mb: int = 256, cpu_seconds: int = 10) -> None:
        self.registry = registry
        self.timeout_seconds = timeout_seconds
        self.memory_mb = memory_mb
        self.cpu_seconds = cpu_seconds

    def invoke(self, manifest: PluginManifest, *, workspace: Path, payload: dict[str, Any], required_permissions: set[PluginPermission] | None = None) -> PluginResult:
        if self.registry.is_disabled(manifest.name):
            raise PermissionError(f"plugin {manifest.name} is disabled")
        for permission in required_permissions or set():
            self.registry.assert_permission(manifest, permission)
        module, sep, callable_name = manifest.entrypoint.partition(":")
        if not sep or not module or not callable_name:
            raise ValueError("isolated plugin entrypoint must be module:callable")
        request = {"entrypoint": manifest.entrypoint, "workspace": str(workspace.resolve()), "permissions": [x.value for x in manifest.permissions], "payload": payload}
        runner = (
            "import importlib,json,sys\n"
            "r=json.load(sys.stdin)\n"
            "m,c=r['entrypoint'].split(':',1)\n"
            "fn=getattr(importlib.import_module(m),c)\n"
            "out=fn({'workspace':r['workspace'],'permissions':r['permissions']},r['payload'])\n"
            "json.dump(out,sys.stdout)\n"
        )
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"}
        preexec = None
        if os.name != "nt":
            def limits() -> None:
                try:
                    import resource
                    setrlimit = getattr(resource, "setrlimit")
                    rlimit_cpu = getattr(resource, "RLIMIT_CPU")
                    rlimit_as = getattr(resource, "RLIMIT_AS")
                    setrlimit(rlimit_cpu, (self.cpu_seconds, self.cpu_seconds + 1))
                    mem = self.memory_mb * 1024 * 1024
                    setrlimit(rlimit_as, (mem, mem))
                except Exception:
                    pass
            preexec = limits
        proc = subprocess.run([sys.executable, "-I", "-c", runner], input=json.dumps(request), text=True, capture_output=True, timeout=self.timeout_seconds, env=env, preexec_fn=preexec, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"plugin process failed: {proc.stderr.strip()[:1000]}")
        raw = json.loads(proc.stdout)
        if not isinstance(raw, dict):
            raise TypeError("isolated plugin output must be a JSON object")
        return PluginResult.model_validate(raw)
