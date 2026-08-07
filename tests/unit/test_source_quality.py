import pytest

from sric.source_quality import SourceProfile, resolve_source_independence


def profile(
    source_id: str,
    *,
    upstream: list[str] | None = None,
    independent: bool = False,
    group: str | None = None,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        source_type="test",
        upstream_source_ids=upstream or [],
        independently_operated=independent,
        declared_independence_group=group,
    )


def test_derived_sources_share_upstream_group() -> None:
    report = resolve_source_independence(
        [
            profile("primary", independent=True),
            profile("mirror-a", upstream=["primary"]),
            profile("mirror-b", upstream=["primary"]),
        ]
    )

    assert report.source_groups["mirror-a"] == report.source_groups["mirror-b"]
    assert report.independent_group_count == 2
    assert report.dependent_sources == ["mirror-a", "mirror-b"]


def test_declared_group_collapses_sources() -> None:
    report = resolve_source_independence(
        [profile("one", group="provider"), profile("two", group="provider")]
    )

    assert report.independent_group_count == 1


def test_unresolved_upstream_is_reported() -> None:
    report = resolve_source_independence(
        [profile("derived", upstream=["missing-provider"])]
    )

    assert report.unresolved_upstreams == {"derived": ["missing-provider"]}
    assert any("unresolved" in item for item in report.limitations)


def test_dependency_cycle_is_conservatively_reported() -> None:
    report = resolve_source_independence(
        [profile("one", upstream=["two"]), profile("two", upstream=["one"])]
    )

    assert report.cycles
    assert any("cycles" in item for item in report.limitations)


def test_generators_are_supported() -> None:
    report = resolve_source_independence(
        profile(value, independent=True) for value in ["one", "two"]
    )

    assert report.independent_group_count == 2


def test_duplicate_source_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        resolve_source_independence([profile("same"), profile("same")])


def test_self_dependency_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot depend on itself"):
        profile("same", upstream=["same"])
