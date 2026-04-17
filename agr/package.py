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
from agr.git import downloaded_repo, safe_get_head_commit
from agr.lockfile import LockedEntry, normalize_parent_ids
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
    parent_sets: dict[str, set[str]] = field(default_factory=dict)
    package_entries: list[LockedEntry] = field(default_factory=list)

    def parent_ids_for(self, identifier: str) -> set[str]:
        """Return the set of parent package IDs for a dep identifier.

        Uses ``parent_sets`` when populated, falling back to the single
        parent in ``parents``.  Direct (non-transitive) deps return an
        empty set.
        """
        parent_set = self.parent_sets.get(identifier)
        if parent_set:
            return set(parent_set)
        parent_id = self.parents.get(identifier)
        return {parent_id} if parent_id else set()


@dataclass
class _QueueItem:
    """An item in the BFS expansion queue."""

    dep: Dependency
    parent_identifier: str | None


def _remote_dep_from_repo_path(
    sub_dep: Dependency,
    repo_dir: Path,
    owner: str,
    repo_name: str,
    source_name: str | None,
) -> Dependency:
    """Convert an in-repo local sub-dependency to a same-repo remote handle."""
    if sub_dep.path is None:
        raise ConfigError("Local dependency is missing path")

    repo_root = repo_dir.resolve()
    resolved_path = (repo_root / sub_dep.path).resolve()
    if not resolved_path.is_relative_to(repo_root):
        raise ConfigError(
            f"Local path dependency '{sub_dep.identifier}' resolves outside "
            "the downloaded repository"
        )
    if resolved_path == repo_root:
        raise ConfigError(
            f"Local path dependency '{sub_dep.identifier}' must point to a "
            "resource directory inside the downloaded repository"
        )
    if resolved_path.parent != repo_root:
        raise ConfigError(
            f"Local path dependency '{sub_dep.identifier}' resolves to a nested "
            "directory. In-repo transitive paths must point to a top-level "
            "resource directory."
        )

    name = resolved_path.name
    return Dependency(
        type=sub_dep.type,
        handle=f"{owner}/{repo_name}/{name}",
        source=source_name,
    )


def _add_package_parent(result: ExpandedDeps, package_id: str, parent_id: str) -> None:
    """Record an additional parent for an already-seen package entry."""
    for entry in result.package_entries:
        if entry.identifier == package_id:
            parent_ids = entry.parent_ids
            parent_ids.add(parent_id)
            entry.parent, entry.parents = normalize_parent_ids(parent_ids)
            return


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
    queued_parents: dict[str, set[str]] = {}
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
            commit = safe_get_head_commit(repo_dir)

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
                if sub_dep.is_local:
                    sub_dep = _remote_dep_from_repo_path(
                        sub_dep, repo_dir, owner, repo_name, source_name
                    )
                sub_id = sub_dep.identifier
                if sub_dep.is_package:
                    queued_parents.setdefault(sub_id, set()).add(identifier)
                    if sub_id in visited:
                        _add_package_parent(result, sub_id, identifier)
                        continue
                    queue.append(_QueueItem(dep=sub_dep, parent_identifier=identifier))
                else:
                    result.parent_sets.setdefault(sub_id, set()).add(identifier)
                    if sub_id not in seen_dep_ids:
                        seen_dep_ids.add(sub_id)
                        result.dependencies.append(sub_dep)
                        result.parents[sub_id] = identifier
                    else:
                        result.parents.setdefault(sub_id, identifier)

            package_parent_ids = queued_parents.get(identifier)
            if package_parent_ids:
                entry = result.package_entries[-1]
                entry.parent, entry.parents = normalize_parent_ids(package_parent_ids)

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
    by_name: dict[tuple[str, str], list[Dependency]] = {}
    for dep in expanded_deps:
        by_name.setdefault((dep.type, dep.installed_name), []).append(dep)

    remove_ids: set[str] = set()
    for (_kind, name), deps in by_name.items():
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
