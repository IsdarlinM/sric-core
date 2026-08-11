from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken


class SecretBackend(Protocol):
    def put(self, secret_id: str, value: str) -> None: ...
    def get(self, secret_id: str) -> str: ...
    def delete(self, secret_id: str) -> None: ...


class KeyringBackend:
    def __init__(self, service: str = "sentinel-forge-sric") -> None:
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("OS keyring backend is unavailable") from exc
        self._keyring = keyring
        self.service = service

    def put(self, secret_id: str, value: str) -> None:
        self._keyring.set_password(self.service, secret_id, value)

    def get(self, secret_id: str) -> str:
        value = self._keyring.get_password(self.service, secret_id)
        if value is None:
            raise KeyError(secret_id)
        return str(value)

    def delete(self, secret_id: str) -> None:
        try:
            self._keyring.delete_password(self.service, secret_id)
        except Exception as exc:
            raise KeyError(secret_id) from exc


class EncryptedFileBackend:
    """Encrypted local fallback. The encryption key is never stored in workspace.json.

    A caller should provide SRIC_VAULT_KEY or persist the generated key in an OS-native keyring.
    """

    def __init__(self, root: Path, key: str | bytes | None = None) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "vault.enc"
        supplied = key or os.environ.get("SRIC_VAULT_KEY")
        self.ephemeral_key: str | None
        if supplied is None:
            self._key = Fernet.generate_key()
            self.ephemeral_key = self._key.decode()
        else:
            raw = supplied.encode() if isinstance(supplied, str) else supplied
            try:
                Fernet(raw)
                self._key = raw
            except Exception:
                self._key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
            self.ephemeral_key = None
        self.fernet = Fernet(self._key)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            decoded = self.fernet.decrypt(self.path.read_bytes())
        except InvalidToken as exc:
            raise PermissionError("vault key cannot decrypt this vault") from exc
        data = json.loads(decoded)
        if not isinstance(data, dict):
            raise ValueError("vault payload is invalid")
        return {str(k): str(v) for k, v in data.items()}

    def _save(self, data: dict[str, str]) -> None:
        self.path.write_bytes(self.fernet.encrypt(json.dumps(data, separators=(",", ":")).encode()))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def put(self, secret_id: str, value: str) -> None:
        data = self._load(); data[secret_id] = value; self._save(data)

    def get(self, secret_id: str) -> str:
        data = self._load()
        if secret_id not in data: raise KeyError(secret_id)
        return data[secret_id]

    def delete(self, secret_id: str) -> None:
        data = self._load()
        if secret_id not in data: raise KeyError(secret_id)
        del data[secret_id]; self._save(data)


@dataclass(frozen=True)
class SecretReference:
    secret_id: str
    backend: str
    label: str


class SecretVault:
    def __init__(self, workspace: Path, backend: SecretBackend | None = None) -> None:
        self.workspace = workspace.resolve()
        self.meta_path = self.workspace / "secrets" / "references.json"
        self.meta_path.parent.mkdir(exist_ok=True)
        if backend is None:
            try:
                backend = KeyringBackend()
                self.backend_name = "os-keyring"
            except RuntimeError:
                backend = EncryptedFileBackend(self.meta_path.parent)
                self.backend_name = "encrypted-file"
        else:
            self.backend_name = backend.__class__.__name__
        self.backend = backend
        if not self.meta_path.exists(): self.meta_path.write_text("[]\n", encoding="utf-8")

    def _refs(self) -> list[dict[str, str]]:
        raw=json.loads(self.meta_path.read_text(encoding="utf-8")); return list(raw) if isinstance(raw,list) else []

    def create(self, label: str, value: str) -> SecretReference:
        if not value: raise ValueError("secret value must not be empty")
        ref=SecretReference(f"SEC-{uuid4().hex.upper()}",self.backend_name,label)
        self.backend.put(ref.secret_id,value)
        refs=self._refs(); refs.append(ref.__dict__); self.meta_path.write_text(json.dumps(refs,indent=2),encoding="utf-8")
        return ref

    def resolve(self, secret_id: str) -> str:
        if secret_id not in {r["secret_id"] for r in self._refs()}: raise KeyError(secret_id)
        return self.backend.get(secret_id)

    def list(self) -> list[SecretReference]:
        return [SecretReference(**x) for x in self._refs()]

    def delete(self, secret_id: str) -> None:
        self.backend.delete(secret_id); refs=[r for r in self._refs() if r["secret_id"]!=secret_id]; self.meta_path.write_text(json.dumps(refs,indent=2),encoding="utf-8")
