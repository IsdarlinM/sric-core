from __future__ import annotations

import sys
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from fastapi import HTTPException

from .errors import debug_exceptions_enabled, safe_exception_message

F = TypeVar("F", bound=Callable[..., Any])

SUPPORTED_WEB_CONTROLS = {
    "text",
    "path",
    "number",
    "flag",
    "tri-state",
    "count",
    "multi-text",
    "multi-value",
    "select",
    "multi-select",
}

WORKBENCH_RECOVERY_JS = r"""
(() => {
  "use strict";

  const output = document.getElementById("output");
  const coverage = document.getElementById("coverage");
  const featureCount = document.getElementById("feature-count");
  const catalogPanel = document.getElementById("catalog-panel");
  const heading = catalogPanel && catalogPanel.querySelector(".section-heading");

  function report(message) {
    const text = String(message || "Interface request failed.");
    if (output && (!output.textContent || output.textContent === "Select an operation to begin." || output.textContent === "Ready.")) {
      output.textContent = text;
    }
    if (coverage && /Loading/i.test(coverage.textContent || "")) {
      coverage.textContent = "Interface unavailable";
      coverage.style.color = "#d77b73";
    }
  }

  if (heading && !document.getElementById("reload-interface")) {
    const recovery = document.createElement("div");
    recovery.style.display = "flex";
    recovery.style.gap = "8px";
    recovery.style.alignItems = "center";
    const health = document.createElement("span");
    health.id = "interface-health";
    health.className = "muted";
    health.style.fontSize = ".7rem";
    health.textContent = "Catalog loading";
    const reload = document.createElement("button");
    reload.id = "reload-interface";
    reload.type = "button";
    reload.className = "ghost";
    reload.textContent = "Reload interface";
    reload.addEventListener("click", () => window.location.reload());
    recovery.append(health, reload);
    heading.append(recovery);

    const observer = new MutationObserver(() => {
      const text = String(coverage ? coverage.textContent : "");
      if (/coverage complete/i.test(text)) {
        health.textContent = "Catalog ready";
        health.style.color = "#74b58c";
      } else if (/gap|unavailable|error/i.test(text)) {
        health.textContent = "Catalog needs attention";
        health.style.color = "#d77b73";
      }
    });
    if (coverage) observer.observe(coverage, {childList: true, subtree: true, characterData: true});
  }

  window.addEventListener("unhandledrejection", event => {
    report("Interface request failed. Review the operation output and use Reload interface to retry.");
    if (event && typeof event.preventDefault === "function") event.preventDefault();
  });
  window.addEventListener("error", () => {
    report("Interface script failed safely. Use Reload interface to restore the capability catalog.");
  });

  window.setTimeout(() => {
    if (coverage && /Loading/i.test(coverage.textContent || "")) {
      report("Capability catalog did not become available. Use Reload interface to retry.");
      if (featureCount) featureCount.textContent = "0 capabilities loaded";
      const health = document.getElementById("interface-health");
      if (health) {
        health.textContent = "Catalog unavailable";
        health.style.color = "#d77b73";
      }
    }
  }, 4000);
})();
""".strip()


def _raise_http_unavailable(label: str, exc: BaseException) -> None:
    if debug_exceptions_enabled():
        raise exc
    raise HTTPException(
        status_code=503,
        detail=f"{label}: {safe_exception_message(exc)}",
    ) from exc


def _validate_feature_catalog(features: list[dict[str, Any]]) -> None:
    seen_paths: set[str] = set()
    seen_ids: set[str] = set()
    for feature in features:
        path = str(feature.get("path") or "")
        feature_id = str(feature.get("id") or "")
        if not path or path in seen_paths:
            raise ValueError("Web feature catalog contains an empty or duplicate command path")
        if not feature_id or feature_id in seen_ids:
            raise ValueError("Web feature catalog contains an empty or duplicate feature id")
        seen_paths.add(path)
        seen_ids.add(feature_id)
        for param in feature.get("params", []):
            control = str(param.get("control") or "")
            if control not in SUPPORTED_WEB_CONTROLS:
                raise ValueError(f"unsupported Web control type: {control or '<empty>'}")
            if not str(param.get("id") or "") or not str(param.get("name") or ""):
                raise ValueError("Web parameter metadata is missing id or name")
            if param.get("kind") == "option" and not param.get("primary_opt"):
                # Paired/flag/count options still need a concrete option token for the fixed runner.
                raise ValueError(f"Web option cannot be mapped to CLI argv: {param.get('name')}")


def _install_feature_builder_guardrails() -> None:
    from . import web_workbench

    if getattr(web_workbench, "_sentinel_feature_guardrails", False):
        return

    original_build = web_workbench.build_feature_catalog
    original_contract = web_workbench.feature_contract

    @wraps(original_build)
    def safe_build(cli_module: str) -> list[dict[str, Any]]:
        try:
            features = original_build(cli_module)
            _validate_feature_catalog(features)
            return features
        except HTTPException:
            raise
        except Exception as exc:
            _raise_http_unavailable("Security Workspace catalog unavailable", exc)

    @wraps(original_contract)
    def safe_contract(cli_module: str) -> dict[str, Any]:
        try:
            payload = original_contract(cli_module)
            if not isinstance(payload, dict):
                raise TypeError("Web interface contract is not an object")
            return payload
        except HTTPException:
            raise
        except Exception as exc:
            _raise_http_unavailable("Security Workspace coverage unavailable", exc)

    web_workbench.build_feature_catalog = safe_build
    web_workbench.feature_contract = safe_contract
    if WORKBENCH_RECOVERY_JS not in web_workbench.WORKBENCH_JS:
        web_workbench.WORKBENCH_JS = web_workbench.WORKBENCH_JS + "\n\n" + WORKBENCH_RECOVERY_JS

    security_workspace = sys.modules.get("sric.web_security_workspace")
    if security_workspace is not None:
        setattr(security_workspace, "build_feature_catalog", safe_build)
        setattr(security_workspace, "feature_contract", safe_contract)
        script = str(getattr(security_workspace, "WORKBENCH_JS", ""))
        if WORKBENCH_RECOVERY_JS not in script:
            setattr(security_workspace, "WORKBENCH_JS", script + "\n\n" + WORKBENCH_RECOVERY_JS)

    setattr(web_workbench, "_sentinel_feature_guardrails", True)


def _install_manager_guardrails() -> None:
    from . import web_console

    manager_type = web_console.WebConsoleManager
    if getattr(manager_type, "_sentinel_endpoint_guardrails", False):
        return

    def wrap_method(
        name: str,
        *,
        label: str,
        expected: tuple[type[BaseException], ...] = (),
    ) -> None:
        original = getattr(manager_type, name)

        @wraps(original)
        def guarded(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                return original(self, *args, **kwargs)
            except (HTTPException, *expected):
                raise
            except Exception as exc:
                _raise_http_unavailable(label, exc)

        setattr(manager_type, name, guarded)

    wrap_method(
        "submit",
        label="operation submission unavailable",
        expected=(ValueError, PermissionError, RuntimeError),
    )
    wrap_method("snapshot", label="operation status unavailable", expected=(KeyError,))
    wrap_method("list_snapshots", label="operation history unavailable")
    wrap_method("cancel", label="operation cancellation unavailable", expected=(KeyError,))

    original_output_since = manager_type.output_since

    @wraps(original_output_since)
    def safe_output_since(
        self: Any, job_id: str, cursor: int
    ) -> tuple[list[str], int, str]:
        try:
            return original_output_since(self, job_id, cursor)
        except KeyError:
            raise
        except Exception as exc:
            if debug_exceptions_enabled():
                raise
            message = "Operation event stream unavailable: " + safe_exception_message(exc) + "\n"
            return [message], max(0, cursor), "failed"

    manager_type.output_since = safe_output_since
    setattr(manager_type, "_sentinel_endpoint_guardrails", True)


def install_web_surface_guardrails() -> None:
    """Install idempotent Web/API error containment and recovery affordances.

    This runs after the fixed-runner and catalog hardening are installed. Expected user
    validation errors keep their normal 4xx contracts; only unexpected runtime failures
    are converted to bounded/redacted 503 responses. SSE failures end as a controlled
    terminal event rather than escaping the ASGI generator.
    """

    _install_feature_builder_guardrails()
    _install_manager_guardrails()
