from __future__ import annotations

from types import SimpleNamespace

import pytest

import sric.runtime_compat as compat


def test_runtime_contract_detects_old_core_and_missing_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compat.importlib.metadata, "version", lambda _name: "0.5.6")
    monkeypatch.setattr(compat.importlib.util, "find_spec", lambda _name: None)

    result = compat.check_runtime_compatibility(
        "sric-core",
        minimum_version="0.5.7",
        maximum_exclusive="0.6.0",
        required_modules=("sric.web_workbench",),
    )

    assert result.compatible is False
    assert result.installed_version == "0.5.6"
    assert result.missing_modules == ("sric.web_workbench",)
    assert any("older than required" in reason for reason in result.reasons)


def test_runtime_repair_upgrades_old_core_then_rechecks(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"version": "0.5.6", "module": False}
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(compat.importlib.metadata, "version", lambda _name: state["version"])
    monkeypatch.setattr(
        compat.importlib.util,
        "find_spec",
        lambda _name: SimpleNamespace() if state["module"] else None,
    )
    monkeypatch.setattr(compat.importlib, "invalidate_caches", lambda: None)

    def fake_update(**kwargs: object) -> object:
        calls.append(kwargs)
        state["version"] = "0.5.7"
        state["module"] = True
        return SimpleNamespace(installed=True)

    monkeypatch.setattr(compat, "perform_product_update", fake_update)

    status = compat.ensure_official_runtime(
        "sric-core",
        minimum_version="0.5.7",
        maximum_exclusive="0.6.0",
        required_modules=("sric.web_workbench",),
    )

    assert status is not None
    assert calls == [
        {
            "expected_product": "sric-core",
            "current_version": "0.5.6",
            "check_only": False,
            "force": False,
        }
    ]


def test_runtime_repair_force_reinstalls_corrupt_same_version(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"module": False}
    seen: dict[str, object] = {}

    monkeypatch.setattr(compat.importlib.metadata, "version", lambda _name: "0.5.7")
    monkeypatch.setattr(
        compat.importlib.util,
        "find_spec",
        lambda _name: SimpleNamespace() if state["module"] else None,
    )
    monkeypatch.setattr(compat.importlib, "invalidate_caches", lambda: None)

    def fake_update(**kwargs: object) -> object:
        seen.update(kwargs)
        state["module"] = True
        return SimpleNamespace(installed=True)

    monkeypatch.setattr(compat, "perform_product_update", fake_update)
    compat.ensure_official_runtime(
        "sric-core",
        minimum_version="0.5.7",
        maximum_exclusive="0.6.0",
        required_modules=("sric.web_workbench",),
    )

    assert seen["force"] is True


def test_runtime_repair_refuses_unsupported_newer_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compat.importlib.metadata, "version", lambda _name: "0.6.0")
    monkeypatch.setattr(compat.importlib.util, "find_spec", lambda _name: None)

    with pytest.raises(RuntimeError, match="newer than the supported compatibility range"):
        compat.ensure_official_runtime(
            "sric-core",
            minimum_version="0.5.7",
            maximum_exclusive="0.6.0",
            required_modules=("sric.web_workbench",),
        )
