from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceAuthority(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    AGGREGATOR = "AGGREGATOR"
    USER_SUPPLIED = "USER_SUPPLIED"
    UNKNOWN = "UNKNOWN"


class SourceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: str
    authority: SourceAuthority = SourceAuthority.UNKNOWN
    independently_operated: bool = False
    upstream_source_ids: list[str] = Field(default_factory=list)
    declared_independence_group: str | None = None
    freshness_seconds: int | None = Field(default=None, ge=0)
    manipulation_risk: float = Field(default=0.5, ge=0.0, le=1.0)
    expected_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    terms_reference: str | None = None
    known_limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_self_dependency(self) -> "SourceProfile":
        if self.source_id in self.upstream_source_ids:
            raise ValueError("a source cannot depend on itself")
        return self


class SourceIndependenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_groups: dict[str, str]
    independent_group_count: int
    dependent_sources: list[str] = Field(default_factory=list)
    unresolved_upstreams: dict[str, list[str]] = Field(default_factory=dict)
    cycles: list[list[str]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def _cycles(profiles: dict[str, SourceProfile]) -> list[list[str]]:
    output: list[list[str]] = []
    active: list[str] = []
    visited: set[str] = set()

    def visit(source_id: str) -> None:
        if source_id in active:
            start = active.index(source_id)
            canonical = active[start:]
            if canonical:
                smallest = min(range(len(canonical)), key=lambda index: canonical[index])
                normalized = canonical[smallest:] + canonical[:smallest]
                normalized.append(normalized[0])
                if normalized not in output:
                    output.append(normalized)
            return
        if source_id in visited:
            return
        active.append(source_id)
        for upstream in profiles[source_id].upstream_source_ids:
            if upstream in profiles:
                visit(upstream)
        active.pop()
        visited.add(source_id)

    for source_id in sorted(profiles):
        visit(source_id)
    return sorted(output)


def resolve_source_independence(
    source_profiles: Iterable[SourceProfile],
) -> SourceIndependenceReport:
    profile_list = list(source_profiles)
    profiles = {profile.source_id: profile for profile in profile_list}
    if not profiles:
        return SourceIndependenceReport(
            source_groups={},
            independent_group_count=0,
            limitations=["No source profiles were supplied."],
        )
    if len(profiles) != len(profile_list):
        raise ValueError("source_id values must be unique")

    cycles = _cycles(profiles)
    cycle_group_by_source: dict[str, str] = {}
    for cycle in cycles:
        members = sorted(set(cycle[:-1]))
        group_id = "cycle:" + ":".join(members)
        for member in members:
            cycle_group_by_source[member] = group_id

    unresolved = {
        source_id: sorted(
            upstream
            for upstream in profile.upstream_source_ids
            if upstream not in profiles
        )
        for source_id, profile in profiles.items()
    }
    unresolved = {key: value for key, value in unresolved.items() if value}

    memo: dict[str, str] = {}

    def group(source_id: str) -> str:
        if source_id in memo:
            return memo[source_id]
        if source_id in cycle_group_by_source:
            result = cycle_group_by_source[source_id]
            memo[source_id] = result
            return result
        profile = profiles[source_id]
        known_upstreams = [
            upstream for upstream in profile.upstream_source_ids if upstream in profiles
        ]
        if known_upstreams:
            upstream_groups = sorted({group(upstream) for upstream in known_upstreams})
            result = "derived:" + "+".join(upstream_groups)
        elif profile.declared_independence_group:
            result = f"declared:{profile.declared_independence_group}"
        elif profile.independently_operated:
            result = f"independent:{source_id}"
        else:
            result = f"unverified:{source_id}"
        memo[source_id] = result
        return result

    groups = {source_id: group(source_id) for source_id in sorted(profiles)}
    dependent = sorted(
        source_id
        for source_id, profile in profiles.items()
        if profile.upstream_source_ids or profile.declared_independence_group
    )
    limitations: list[str] = []
    if unresolved:
        limitations.append(
            "Some upstream sources are unresolved; independence is not established for those chains."
        )
    if cycles:
        limitations.append(
            "Source dependency cycles were detected and conservatively grouped together."
        )
    if any(value.startswith("unverified:") for value in groups.values()):
        limitations.append(
            "Sources without upstream metadata or independent-operation evidence remain unverified groups."
        )

    return SourceIndependenceReport(
        source_groups=groups,
        independent_group_count=len(set(groups.values())),
        dependent_sources=dependent,
        unresolved_upstreams=unresolved,
        cycles=cycles,
        limitations=limitations,
    )
