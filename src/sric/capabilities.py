from __future__ import annotations

from importlib import metadata
from typing import Callable, Iterable

from pydantic import BaseModel, ConfigDict, Field


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
    version: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    optional_integrations: list[str] = Field(default_factory=list)


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_distribution: str = "sric-core"
    core_version: str
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


def discover_capabilities(
    *,
    current_product: str | None = None,
    version_resolver: Callable[[str], str | None] = _resolve_version,
    products: Iterable[ProductDefinition] = PRODUCTS,
) -> CapabilityReport:
    core_version = version_resolver("sric-core") or "unknown"
    statuses: list[ProductCapabilityStatus] = []
    available: set[str] = set()
    current_installed = current_product is None

    for definition in products:
        version = version_resolver(definition.distribution)
        installed = version is not None
        if installed:
            available.update(definition.capabilities)
        if definition.product == current_product:
            current_installed = installed
        statuses.append(
            ProductCapabilityStatus(
                product=definition.product,
                distribution=definition.distribution,
                installed=installed,
                version=version,
                capabilities=list(definition.capabilities) if installed else [],
                optional_integrations=list(definition.optional_integrations),
            )
        )

    return CapabilityReport(
        core_version=core_version,
        current_product=current_product,
        standalone_ready=core_version != "unknown" and current_installed,
        products=statuses,
        available_capabilities=sorted(available),
    )


def integration_available(capability: str, report: CapabilityReport) -> bool:
    return capability in report.available_capabilities
