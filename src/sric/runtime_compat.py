from __future__ import annotations

import importlib.metadata
import importlib.util
from dataclasses import dataclass

from .updater import UpdateCheck, _compare_semver, perform_product_update


@dataclass(frozen=True)
class RuntimeCompatibility:
    product: str
    installed_version: str | None
    minimum_version: str
    maximum_exclusive: str | None
    required_modules: tuple[str, ...]
    missing_modules: tuple[str, ...]
    compatible: bool
    reasons: tuple[str, ...]


def check_runtime_compatibility(
    product: str,
    *,
    minimum_version: str,
    maximum_exclusive: str | None = None,
    required_modules: tuple[str, ...] = (),
) -> RuntimeCompatibility:
    reasons: list[str] = []
    try:
        installed = importlib.metadata.version(product)
    except importlib.metadata.PackageNotFoundError:
        installed = None
        reasons.append(f"{product} is not installed")

    if installed is not None:
        if _compare_semver(installed, minimum_version) < 0:
            reasons.append(
                f"{product} {installed} is older than required {minimum_version}"
            )
        if maximum_exclusive is not None and _compare_semver(installed, maximum_exclusive) >= 0:
            reasons.append(
                f"{product} {installed} is outside the supported range (<{maximum_exclusive})"
            )

    missing = tuple(
        module for module in required_modules if importlib.util.find_spec(module) is None
    )
    if missing:
        reasons.append("missing runtime modules: " + ", ".join(missing))

    return RuntimeCompatibility(
        product=product,
        installed_version=installed,
        minimum_version=minimum_version,
        maximum_exclusive=maximum_exclusive,
        required_modules=required_modules,
        missing_modules=missing,
        compatible=not reasons,
        reasons=tuple(reasons),
    )


def ensure_official_runtime(
    product: str,
    *,
    minimum_version: str,
    maximum_exclusive: str | None = None,
    required_modules: tuple[str, ...] = (),
) -> UpdateCheck | None:
    """Repair an installed first-party runtime from its signed official channel.

    The function is intentionally narrow: it only repairs an already-installed
    Sentinel Forge package through the same signed-commit updater used by public
    `update` commands. It never installs an arbitrary package or URL.
    """

    before = check_runtime_compatibility(
        product,
        minimum_version=minimum_version,
        maximum_exclusive=maximum_exclusive,
        required_modules=required_modules,
    )
    if before.compatible:
        return None
    if before.installed_version is None:
        raise RuntimeError(
            f"{product} is missing; reinstall the product so first-party dependencies are bootstrapped"
        )
    if maximum_exclusive is not None and _compare_semver(
        before.installed_version, maximum_exclusive
    ) >= 0:
        raise RuntimeError("installed first-party runtime is newer than the supported compatibility range")

    force = (
        _compare_semver(before.installed_version, minimum_version) >= 0
        and bool(before.missing_modules)
    )
    status = perform_product_update(
        expected_product=product,
        current_version=before.installed_version,
        check_only=False,
        force=force,
    )
    importlib.invalidate_caches()

    after = check_runtime_compatibility(
        product,
        minimum_version=minimum_version,
        maximum_exclusive=maximum_exclusive,
        required_modules=required_modules,
    )
    if not after.compatible:
        raise RuntimeError(
            "first-party runtime repair completed but compatibility verification still failed: "
            + "; ".join(after.reasons)
        )
    return status
