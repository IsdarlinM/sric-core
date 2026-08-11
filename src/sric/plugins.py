from __future__ import annotations

import hashlib
import json
import builtins
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PluginType(StrEnum):
    COLLECTOR="collector"; IMPORTER="importer"; EXPORTER="exporter"; ANALYZER="analyzer"; VALIDATOR="validator"; AI_PROVIDER="ai_provider"; REPORTER="reporter"; VISUALIZER="visualizer"; INTEGRATION="integration"

class PluginPermission(StrEnum):
    NETWORK="network"; FILESYSTEM_READ="filesystem_read"; FILESYSTEM_WRITE="filesystem_write"; WORKSPACE_ACCESS="workspace_access"; SECRETS="secrets"; CLOUD_AI="cloud_ai"; AI="ai"; ACTIVE_REQUESTS="active_requests"

class PluginManifest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(pattern=r"^[a-zA-Z0-9_.-]+$"); version:str; api_version:str="2"; type:PluginType
    permissions:set[PluginPermission]=Field(default_factory=set); capabilities:list[str]=Field(default_factory=list); entrypoint:str
    publisher:str|None=None; artifact_sha256:str|None=Field(default=None,pattern=r"^[a-f0-9]{64}$"); signature:str|None=None

class PluginRegistry:
    def __init__(self,manifests_dir:Path)->None:
        self.manifests_dir=manifests_dir; self.manifests_dir.mkdir(parents=True,exist_ok=True); self.disabled_dir=self.manifests_dir/".disabled"; self.disabled_dir.mkdir(exist_ok=True)
    def list(self,*,include_disabled:bool=True)->list[PluginManifest]:
        manifests=[]
        for path in sorted(self.manifests_dir.glob("*.json")):
            manifest=PluginManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if include_disabled or not self.is_disabled(manifest.name): manifests.append(manifest)
        return manifests
    def inspect(self,name:str)->PluginManifest:
        for manifest in self.list():
            if manifest.name==name:return manifest
        raise KeyError(name)
    def install_manifest(self,source:Path)->PluginManifest:
        if not source.is_file() or source.is_symlink():raise ValueError("plugin manifest must be a regular non-symlink file")
        if source.stat().st_size>1024*1024:raise ValueError("plugin manifest exceeds 1 MiB limit")
        manifest=PluginManifest.model_validate(json.loads(source.read_text(encoding="utf-8")));target=self.manifests_dir/f"{manifest.name}.json"
        if target.exists():raise FileExistsError(f"plugin already installed: {manifest.name}")
        target.write_text(manifest.model_dump_json(indent=2),encoding="utf-8");return manifest
    def remove(self,name:str)->None:
        path=self.manifests_dir/f"{name}.json"
        if not path.is_file():raise KeyError(name)
        path.unlink();disabled=self.disabled_dir/name
        if disabled.exists():disabled.unlink()
    def disable(self,name:str)->None:self.inspect(name);(self.disabled_dir/name).write_text("disabled\n",encoding="utf-8")
    def enable(self,name:str)->None:self.inspect(name);(self.disabled_dir/name).unlink(missing_ok=True)
    def is_disabled(self,name:str)->bool:return (self.disabled_dir/name).exists()
    def verify(self,name:str)->dict[str,object]:
        manifest=self.inspect(name);path=self.manifests_dir/f"{name}.json";digest=hashlib.sha256(path.read_bytes()).hexdigest()
        return {"name":manifest.name,"version":manifest.version,"api_version":manifest.api_version,"sha256":digest,"disabled":self.is_disabled(name),"permissions":sorted(x.value for x in manifest.permissions),"publisher":manifest.publisher,"artifact_sha256":manifest.artifact_sha256,"signed":bool(manifest.signature),"valid":True}
    def verify_artifact(self,name:str,artifact:Path)->dict[str,object]:
        manifest=self.inspect(name)
        if not artifact.is_file() or artifact.is_symlink():raise ValueError("plugin artifact must be a regular non-symlink file")
        digest=hashlib.sha256(artifact.read_bytes()).hexdigest();expected=manifest.artifact_sha256
        return {"name":name,"sha256":digest,"expected_sha256":expected,"hash_valid":expected is not None and digest==expected,"signature_declared":bool(manifest.signature),"publisher":manifest.publisher,"execution_allowed":expected is not None and digest==expected and not self.is_disabled(name),"note":"Signature field is provenance metadata until a configured trust-root verifier validates it."}
    def permission_diff(self,old:PluginManifest,new:PluginManifest)->dict[str,builtins.list[str]]:return {"added":sorted(x.value for x in new.permissions-old.permissions),"removed":sorted(x.value for x in old.permissions-new.permissions)}
    def assert_permission(self,manifest:PluginManifest,permission:PluginPermission)->None:
        if self.is_disabled(manifest.name):raise PermissionError(f"plugin {manifest.name} is disabled")
        if permission not in manifest.permissions:raise PermissionError(f"plugin {manifest.name} lacks declared permission: {permission}")
