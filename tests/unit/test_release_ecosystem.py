from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "release-ecosystem.py"
    spec = importlib.util.spec_from_file_location("release_ecosystem", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_semantic_version_constraints() -> None:
    module = load_script()

    assert module.compatible("0.4.1", ">=0.4.1,<0.5") is True
    assert module.compatible("0.4.0", ">=0.4.1,<0.5") is False
    assert module.compatible("0.5.0", ">=0.4.1,<0.5") is False
    assert module.compatible("0.4.1", None) is False


def test_unsupported_versions_fail_closed() -> None:
    module = load_script()

    with pytest.raises(ValueError, match="unsupported semantic version"):
        module.version_tuple("0.4")


def test_dependency_spec_is_extracted() -> None:
    module = load_script()
    metadata = {
        "dependencies": [
            "fastapi>=0.128,<1",
            "sric-core>=0.4.1,<0.5",
        ]
    }

    assert module.dependency_spec(metadata, "sric-core") == ">=0.4.1,<0.5"
    assert module.dependency_spec(metadata, "reprosec") is None


def test_release_order_is_dependency_first() -> None:
    module = load_script()

    assert module.REPOSITORIES[0] == "sric-core"
    assert module.REPOSITORIES[1] == "reprosec"
    assert module.REPOSITORIES[-1] == "exposuredna"
