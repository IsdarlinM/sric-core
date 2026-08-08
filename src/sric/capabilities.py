from __future__ import annotations

from importlib import metadata
from typing import Callable, Iterable

from pydantic import BaseModel, ConfigDict, Field


SUPPORTED_TRAIN = (0, 5)


class ProductDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product: str
    distribution: str
    capabilities: tuple[str, ...]
    optional_integrations: tuple[str, ...] = ()


class ProductCapabilityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str
    distribution: str
    installed: bool
    compatible: bool
    version: str | None = None
    compatibility_reason: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    optional_integrations: list[str] = Field(default_factory=list)


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_distribution: str = "sric-core"
    core_version: str
    core_compatible: bool
    current_product: str | None = None
    standalone_ready: bool = True
    products: list[ProductCapabilityStatus] = Field(default_factory=list)
    available_capabilities: list[str] = Field(default_factory=list)


PRODUCTS: tuple[ProductDefinition, ...] = (
    ProductDefinition(
        product="reprosec",
        distribution="reprosec",
        capabilities=("rcap.evidence", "rcap.replay", "validation.deterministic"),
        optional_integrations=("authorization.model", "temporal.archaeology", "trust.paths", "organization.resolution"),
    ),
    ProductDefinition(
        product="authtwin",
        distribution="authtwin",
        capabilities=("authorization.model", "authorization.coverage", "authorization.differential"),
        optional_integrations=("rcap.evidence", "trust.paths"),
    ),
    ProductDefinition(
        product="fossilscope",
        distribution="fossilscope",
        capabilities=("temporal.archaeology", "temporal.reobservation", "api.evolution"),
        optional_integrations=("organization.resolution", "trust.paths", "authorization.model", "rcap.evidence"),
    ),
    ProductDefinition(
        product="trustboundary",
        distribution="trustboundary",
        capabilities=("trust.paths", "trust.invariants", "identity.provenance"),
        optional_integrations=("authorization.model", "temporal.archaeology", "organization.resolution"),
    ),
    ProductDefinition(
        product="exposuredna",
        distribution="exposuredna",
        capabilities=("organization.resolution", "organization.temporal", "organization.graph"),
        optional_integrations=("temporal.archaeology", "trust.paths", "authorization.model"),
    ),
)


def _resolve_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def _train(version: str | None) -> tuple[int, int] | None:
    if not version:
        return None
    core = version.split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    return int(parts[0]), int(parts[1])


def _compatibility(version: str | None) -> tuple[bool, str | None]:
    if version is None:
        return False, "not installed"
    train = _train(version)
    if train is None:
        return False, "version is not a supported semantic version"
    if train != SUPPORTED_TRAIN:
        return False, f"requires the {SUPPORTED_TRAIN[0]}.{SUPPORTED_TRAIN[1]}.x release train"
    return True, None


def discover_capabilities(
    *,
    current_product: str | None = None,
    version_resolver: Callable[[str], str | None] = _resolve_version,
    products: Iterable[ProductDefinition] = PRODUCTS,
) -> CapabilityReport:
    core_version = version_resolver("sric-core") or "unknown"
    core_compatible, _ = _compatibility(None if core_version == "unknown" else core_version)
    statuses: list[ProductCapabilityStatus] = []
    available: set[str] = set()
    current_compatible = current_product is None

    for definition in products:
        version = version_resolver(definition.distribution)
        installed = version is not None
        compatible, reason = _compatibility(version)
        usable = installed and compatible and core_compatible
        if usable:
            available.update(definition.capabilities)
        if definition.product == current_product:
            current_compatible = usable
        statuses.append(
            ProductCapabilityStatus(
                product=definition.product,
                distribution=definition.distribution,
                installed=installed,
                compatible=usable,
                version=version,
                compatibility_reason=(
                    reason
                    if not compatible
                    else (None if core_compatible else "installed SRIC Core is outside the 0.5.x release train")
                ),
                capabilities=list(definition.capabilities) if usable else [],
                optional_integrations=list(definition.optional_integrations),
            )
        )

    return CapabilityReport(
        core_version=core_version,
        core_compatible=core_compatible,
        current_product=current_product,
        standalone_ready=core_compatible and current_compatible,
        products=statuses,
        available_capabilities=sorted(available),
    )


def integration_available(capability: str, report: CapabilityReport) -> bool:
    return capability in report.available_capabilities
