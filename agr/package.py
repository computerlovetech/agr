"""Package expansion and transitive dependency resolution.

A *package* is a content-less bundle that pulls in other skills, ralphs,
or nested packages via its own ``agr.toml``.  This module walks the
dependency DAG, flattens it into a list of leaf dependencies (skills and
ralphs), and detects conflicts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from agr.config import (
    CONFIG_FILENAME,
    AgrConfig,
    Dependency,
)
from agr.exceptions import ConfigError, PackageConflictError
from agr.git import downloaded_repo, get_head_commit_full
from agr.lockfile import LockedEntry
from agr.source import SourceResolver


def load_sub_deps(resource_dir: Path) -> list[Dependency]:
    """Load dependencies from a resource's agr.toml, if present.

    Uses ``AgrConfig.load_sub_manifest`` so consumer-only fields
    (tools, sources, etc.) are ignored.
    """
    manifest = resource_dir / CONFIG_FILENAME
    if not manifest.exists():
        return []
    config = AgrConfig.load_sub_manifest(manifest)
    return config.dependencies


def has_package_section(resource_dir: Path) -> bool:
    """Check whether a resource directory has a [package] section in agr.toml."""
    manifest = resource_dir / CONFIG_FILENAME
    if not manifest.exists():
        return False
    config = AgrConfig.load_sub_manifest(manifest)
    return config.package is not None


@dataclass
class ExpandedDeps:
    """Result of expanding packages into a flat dependency list."""

    dependencies: list[Dependency] = field(default_factory=list)
    parents: dict[str, str] = field(default_factory=dict)
    package_entries: list[LockedEntry] = field(default_factory=list)


@dataclass
class _QueueItem:
    """An item in the BFS expansion queue."""

    dep: Dependency
    parent_identifier: str | None


def expand_packages(
    direct_deps: list[Dependency],
    resolver: SourceResolver,
    default_source: str,
    default_owner: str | None,
    default_repo: str | None,
) -> ExpandedDeps:
    """Expand package dependencies into a flat list of skills and ralphs.

    Walks the dependency DAG breadth-first. For each ``type="package"``
    dependency, downloads the repo, reads the sub-manifest, and collects
    its sub-deps.  Leaf deps (skills/ralphs) are added to the flat
    output list.  Packages are recorded as ``package_entries`` for the
    lockfile.

    Direct deps that are already skills/ralphs pass through unchanged.
    """
    result = ExpandedDeps()
    visited: set[str] = set()
    queue: deque[_QueueItem] = deque()

    for dep in direct_deps:
        if dep.is_package:
            queue.append(_QueueItem(dep=dep, parent_identifier=None))
        else:
            result.dependencies.append(dep)

    # Track seen dependency identifiers to avoid duplicates without
    # rebuilding a set from result.dependencies on every iteration.
    seen_dep_ids: set[str] = {d.identifier for d in result.dependencies}

    while queue:
        item = queue.popleft()
        dep = item.dep
        identifier = dep.identifier

        if identifier in visited:
            continue
        visited.add(identifier)

        handle = dep.to_parsed_handle(default_owner)
        source_name = dep.resolve_source_name(default_source)

        if handle.is_local:
            raise ConfigError(f"Local packages are not supported: '{dep.identifier}'")

        source_config = resolver.get(source_name or default_source)
        owner, repo_name = handle.get_github_repo(default_repo=default_repo)

        with downloaded_repo(source_config, owner, repo_name) as repo_dir:
            commit = _safe_get_commit(repo_dir)

            sub_dir = repo_dir / handle.name
            if not sub_dir.is_dir():
                raise ConfigError(
                    f"Package '{dep.identifier}' not found: "
                    f"directory '{handle.name}' does not exist in "
                    f"'{owner}/{repo_name}'"
                )

            sub_deps = load_sub_deps(sub_dir)

            result.package_entries.append(
                LockedEntry(
                    handle=dep.handle,
                    source=source_name,
                    commit=commit,
                    installed_name=dep.installed_name,
                    parent=item.parent_identifier,
                )
            )

            for sub_dep in sub_deps:
                sub_id = sub_dep.identifier
                if sub_dep.is_package:
                    if sub_id in visited:
                        continue
                    queue.append(_QueueItem(dep=sub_dep, parent_identifier=identifier))
                else:
                    if sub_id not in seen_dep_ids:
                        seen_dep_ids.add(sub_id)
                        result.dependencies.append(sub_dep)
                        result.parents[sub_id] = identifier

    return result


def detect_conflicts(
    expanded_deps: list[Dependency],
    parents: dict[str, str],
    direct_identifiers: set[str],
) -> list[Dependency]:
    """Detect and resolve conflicts among expanded dependencies.

    Groups dependencies by ``installed_name``. When two deps share the
    same installed name but have different identifiers:

    - If one is a direct dep (from the consumer's agr.toml), it wins
      and the transitive one is removed.
    - If both are transitive, raises ``PackageConflictError``.

    Returns the (possibly pruned) dependency list.
    """
    by_name: dict[str, list[Dependency]] = {}
    for dep in expanded_deps:
        by_name.setdefault(dep.installed_name, []).append(dep)

    remove_ids: set[str] = set()
    for name, deps in by_name.items():
        if len(deps) <= 1:
            continue

        unique_ids = {d.identifier for d in deps}
        if len(unique_ids) <= 1:
            continue

        direct = [d for d in deps if d.identifier in direct_identifiers]
        transitive = [d for d in deps if d.identifier not in direct_identifiers]

        if len(direct) == 1:
            for t in transitive:
                remove_ids.add(t.identifier)
            continue

        if len(direct) > 1:
            raise PackageConflictError(
                f"Conflict: multiple direct dependencies install as '{name}': "
                + ", ".join(d.identifier for d in direct)
            )

        parent_info = [
            f"'{d.identifier}' (via {parents.get(d.identifier, '?')})"
            for d in transitive
        ]
        raise PackageConflictError(
            f"Conflict: multiple transitive dependencies install as '{name}': "
            + ", ".join(parent_info)
            + ". Add the preferred one directly to your agr.toml to resolve."
        )

    if remove_ids:
        expanded_deps = [d for d in expanded_deps if d.identifier not in remove_ids]
        for rid in remove_ids:
            parents.pop(rid, None)

    return expanded_deps


def _safe_get_commit(repo_dir: Path) -> str | None:
    """Get the HEAD commit SHA, returning None on failure."""
    try:
        return get_head_commit_full(repo_dir)
    except Exception:
        return None
