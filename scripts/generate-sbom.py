#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tomllib
import uuid
from importlib import metadata
from pathlib import Path
from typing import Iterable

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def canonical(name: str) -> str:
    return name.lower().replace('_', '-').replace('.', '-')


def project_metadata() -> tuple[str, str, list[str]]:
    data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    project = data['project']
    return str(project['name']), str(project['version']), list(project.get('dependencies', []))


def installed_distribution(name: str):
    try:
        return metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return None


def active_requirements(requirements: Iterable[str]) -> list[Requirement]:
    out: list[Requirement] = []
    for raw in requirements:
        req = Requirement(raw)
        if req.marker is None or req.marker.evaluate():
            out.append(req)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a project-scoped CycloneDX SBOM from installed runtime dependencies.')
    parser.add_argument('--output', default='sbom.cdx.json')
    args = parser.parse_args()

    project_name, project_version, root_requirements = project_metadata()
    root_ref = f'pkg:pypi/{canonical(project_name)}@{project_version}'
    components: dict[str, dict[str, object]] = {}
    dependency_edges: dict[str, set[str]] = {root_ref: set()}
    queue = active_requirements(root_requirements)
    seen: set[str] = set()

    while queue:
        req = queue.pop(0)
        key = canonical(req.name)
        if key in seen:
            continue
        seen.add(key)
        dist = installed_distribution(req.name)
        if dist is None:
            ref = f'pkg:pypi/{key}'
            components[ref] = {
                'type': 'library',
                'name': req.name,
                'bom-ref': ref,
                'properties': [
                    {'name': 'sric:resolution', 'value': 'not-installed-in-generator-environment'},
                    {'name': 'sric:declared-requirement', 'value': str(req)},
                ],
            }
            root_ref_for_dep = ref
            dependency_edges.setdefault(ref, set())
        else:
            ref = f'pkg:pypi/{key}@{dist.version}'
            components[ref] = {
                'type': 'library',
                'name': dist.metadata.get('Name') or req.name,
                'version': dist.version,
                'bom-ref': ref,
                'purl': ref,
            }
            dependency_edges.setdefault(ref, set())
            child_reqs = active_requirements(dist.requires or [])
            for child in child_reqs:
                child_dist = installed_distribution(child.name)
                child_key = canonical(child.name)
                child_ref = (
                    f'pkg:pypi/{child_key}@{child_dist.version}' if child_dist is not None else f'pkg:pypi/{child_key}'
                )
                dependency_edges[ref].add(child_ref)
                queue.append(child)
            root_ref_for_dep = ref
        # Only direct declared requirements are linked from the project root here.
        if any(canonical(d.name) == key for d in active_requirements(root_requirements)):
            dependency_edges[root_ref].add(root_ref_for_dep)

    payload = {
        'bomFormat': 'CycloneDX',
        'specVersion': '1.5',
        'serialNumber': f'urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, root_ref)}',
        'version': 1,
        'metadata': {
            'component': {
                'type': 'application',
                'name': project_name,
                'version': project_version,
                'bom-ref': root_ref,
                'purl': root_ref,
            },
            'tools': [{'vendor': 'SRIC', 'name': 'project-scoped-stdlib-sbom-generator'}],
        },
        'components': sorted(components.values(), key=lambda c: str(c['bom-ref'])),
        'dependencies': [
            {'ref': ref, 'dependsOn': sorted(deps)}
            for ref, deps in sorted(dependency_edges.items())
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
