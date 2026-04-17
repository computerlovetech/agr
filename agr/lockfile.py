"""Lockfile management for reproducible skill installs.

The lockfile (agr.lock) pins exact git commit SHAs for every resolved
dependency so that ``agr sync`` produces identical results across
machines and over time.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import tomlkit
import tomlkit.items
from tomlkit import TOMLDocument
from tomlkit.exceptions import TOMLKitError

from agr.config import (
    DEPENDENCY_TYPE_PACKAGE,
    DEPENDENCY_TYPE_RALPH,
    DEPENDENCY_TYPE_SKILL,
    Dependency,
)
from agr.exceptions import ConfigError

LOCKFILE_FILENAME = "agr.lock"
LOCKFILE_VERSION = 1


def normalize_parent_ids(
    parent_ids: set[str] | None,
) -> tuple[str | None, list[str] | None]:
    """Normalize a set of parent package ids into ``(parent, parents)`` fields.

    Returns ``(None, None)`` for no parents, ``(id, None)`` for exactly one,
    and ``(None, sorted_ids)`` for multiple — matching the ``LockedEntry``
    TOML schema where a single parent uses the scalar ``parent`` key and
    multiple parents use the ``parents`` array.
    """
    if not parent_ids:
        return None, None
    sorted_ids = sorted(parent_ids)
    if len(sorted_ids) == 1:
        return sorted_ids[0], None
    return None, sorted_ids


@dataclass
class LockedEntry:
    """A single locked dependency entry.

    Remote skills have handle/source/commit/content_hash.
    Local skills have path only (resolved from disk at sync time).
    Both have installed_name.
    """

    installed_name: str
    # Remote fields
    handle: str | None = None
    source: str | None = None
    commit: str | None = None
    content_hash: str | None = None
    # Local field
    path: str | None = None
    # Transitive dependency annotation (identifier of the parent package)
    parent: str | None = None
    # Multiple parent packages can share the same transitive dependency.
    parents: list[str] | None = None

    # TOML key for the required installed-name field.
    _TOML_KEY_INSTALLED_NAME: ClassVar[str] = "installed-name"

    # Mapping from dataclass field names to TOML key names.
    # Order defines the serialization order in the lockfile.
    _TOML_OPTIONAL_FIELDS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("handle", "handle"),
        ("path", "path"),
        ("source", "source"),
        ("commit", "commit"),
        ("content_hash", "content-hash"),
    )

    @property
    def is_local(self) -> bool:
        return self.path is not None

    @property
    def identifier(self) -> str:
        """Unique identifier matching Dependency.identifier."""
        return self.path or self.handle or ""

    @property
    def parent_ids(self) -> set[str]:
        """Return all package parents recorded for this entry."""
        ids: set[str] = set()
        if self.parent:
            ids.add(self.parent)
        if self.parents:
            ids.update(self.parents)
        return ids

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LockedEntry:
        """Deserialize a TOML table into a LockedEntry."""

        def _get_optional_str(key: str) -> str | None:
            value = data.get(key)
            return str(value) if value is not None else None

        kwargs: dict[str, str | None] = {
            attr: _get_optional_str(toml_key)
            for attr, toml_key in cls._TOML_OPTIONAL_FIELDS
        }
        parent = _get_optional_str("parent")
        raw_parents = data.get("parents")
        parents: list[str] | None = None
        if isinstance(raw_parents, Iterable) and not isinstance(raw_parents, str):
            parents = [str(value) for value in raw_parents]

        # Security: reject local-path entries that claim a package parent.
        # Legitimate sync never produces these — expand_packages() converts
        # local sub-deps inside a remote package to same-repo remote handles
        # (see SF-006). A local path + parent combination can only arise via
        # lockfile tampering and would install from an arbitrary filesystem
        # location in --frozen mode, bypassing the SF-006 safeguard.
        if kwargs.get("path") is not None and (parent or parents):
            raise ConfigError(
                f"Lockfile entry has both 'path' and a package parent "
                f"(path={kwargs.get('path')!r}). Local-path transitive "
                "dependencies are not allowed; the lockfile may be "
                "corrupted or tampered with."
            )

        return cls(
            installed_name=str(data.get(cls._TOML_KEY_INSTALLED_NAME, "")),
            parent=parent,
            parents=parents,
            **kwargs,
        )

    def to_toml_table(self) -> tomlkit.items.Table:
        """Serialize this entry into a tomlkit Table."""
        table = tomlkit.table()
        for attr, key in self._TOML_OPTIONAL_FIELDS:
            value = getattr(self, attr)
            if value is not None:
                table[key] = value
        parent, parents = normalize_parent_ids(self.parent_ids)
        if parent is not None:
            table["parent"] = parent
        if parents is not None:
            table["parents"] = parents
        table[self._TOML_KEY_INSTALLED_NAME] = self.installed_name
        return table


@dataclass
class Lockfile:
    """The full lockfile state."""

    # Valid section keys, matching TOML section names and Dependency.type values.
    SECTION_KEYS: ClassVar[tuple[str, ...]] = (
        DEPENDENCY_TYPE_SKILL,
        DEPENDENCY_TYPE_RALPH,
        DEPENDENCY_TYPE_PACKAGE,
    )

    version: int = LOCKFILE_VERSION
    skills: list[LockedEntry] = field(default_factory=list)
    ralphs: list[LockedEntry] = field(default_factory=list)
    packages: list[LockedEntry] = field(default_factory=list)

    def _entries(self, kind: str = DEPENDENCY_TYPE_SKILL) -> list[LockedEntry]:
        """Return the entries list for a given kind.

        Args:
            kind: ``"skill"``, ``"ralph"``, or ``"package"``.

        Raises:
            ValueError: If *kind* is not a recognized section key.
        """
        if kind == DEPENDENCY_TYPE_SKILL:
            return self.skills
        if kind == DEPENDENCY_TYPE_RALPH:
            return self.ralphs
        if kind == DEPENDENCY_TYPE_PACKAGE:
            return self.packages
        raise ValueError(f"Unknown lockfile entry kind: {kind!r}")

    def installed_entries(self) -> Iterator[LockedEntry]:
        """Iterate over all entries representing installed resources.

        Yields skill and ralph entries — the resource types that are
        actually installed on disk.  Packages are excluded because they
        are virtual bundles (content-less parents in the dependency tree).
        """
        yield from self.skills
        yield from self.ralphs

    def update_entry(
        self, entry: LockedEntry, *, kind: str = DEPENDENCY_TYPE_SKILL
    ) -> None:
        """Add or replace an entry by identifier."""
        entries = self._entries(kind)
        entries[:] = [e for e in entries if e.identifier != entry.identifier]
        entries.append(entry)

    def remove_entry(
        self, identifier: str, *, kind: str = DEPENDENCY_TYPE_SKILL
    ) -> bool:
        """Remove an entry by identifier.

        Returns True if an entry was removed, False if no match was found.
        """
        entries = self._entries(kind)
        original_len = len(entries)
        entries[:] = [e for e in entries if e.identifier != identifier]
        return len(entries) < original_len

    def find_entry(self, dep: Dependency) -> LockedEntry | None:
        """Look up a dependency's entry."""
        identifier = dep.identifier
        for entry in self._entries(dep.type):
            if entry.identifier == identifier:
                return entry
        return None

    def package_closure(self, package_ids: set[str]) -> set[str]:
        """Return package ids including nested packages whose parent is included.

        Expands *package_ids* by iteratively adding any package entry whose
        parent chain intersects the current set, until a fixed point is
        reached.
        """
        all_pkg_ids = set(package_ids)
        changed = True
        while changed:
            changed = False
            for entry in self.packages:
                if (
                    entry.parent_ids & all_pkg_ids
                    and entry.identifier not in all_pkg_ids
                ):
                    all_pkg_ids.add(entry.identifier)
                    changed = True
        return all_pkg_ids

    def is_current(self, dependencies: list[Dependency]) -> bool:
        """Check if the lockfile covers exactly the same deps as agr.toml.

        Returns True only if the lockfile has entries for all dependencies
        and no extra entries. Does not check whether SHAs are stale.

        Transitive entries (those with a ``parent`` field) are excluded
        from the comparison because they originate from package expansion
        at sync time and are not listed in agr.toml directly.
        """
        for kind in self.SECTION_KEYS:
            lockfile_ids = {
                e.identifier for e in self._entries(kind) if not e.parent_ids
            }
            config_ids = {d.identifier for d in dependencies if d.type == kind}
            if lockfile_ids != config_ids:
                return False
        return True


def build_lockfile_path(config_path: Path) -> Path:
    """Return the lockfile path alongside the given config path."""
    return config_path.parent / LOCKFILE_FILENAME


def _parse_locked_entries(doc: TOMLDocument, key: str) -> list[LockedEntry]:
    """Parse locked entries from a TOML section."""
    entries: list[LockedEntry] = []
    for item in doc.get(key, []):
        if not isinstance(item, dict):
            continue
        entries.append(LockedEntry.from_dict(item))
    return entries


def load_lockfile(path: Path) -> Lockfile | None:
    """Load a lockfile from disk.

    Returns None if the file does not exist.
    Raises ConfigError if the file is malformed.
    """
    if not path.exists():
        return None

    try:
        content = path.read_text()
        doc = tomlkit.parse(content)
    except (TOMLKitError, OSError) as e:
        raise ConfigError(f"Invalid lockfile {path}: {e}") from e

    version = doc.get("version", LOCKFILE_VERSION)
    if version != LOCKFILE_VERSION:
        raise ConfigError(
            f"Unsupported lockfile version {version} (expected {LOCKFILE_VERSION})"
        )

    skills = _parse_locked_entries(doc, DEPENDENCY_TYPE_SKILL)
    ralphs = _parse_locked_entries(doc, DEPENDENCY_TYPE_RALPH)
    packages = _parse_locked_entries(doc, DEPENDENCY_TYPE_PACKAGE)

    return Lockfile(version=version, skills=skills, ralphs=ralphs, packages=packages)


def save_lockfile(lockfile: Lockfile, path: Path) -> None:
    """Write a lockfile to disk."""
    doc: TOMLDocument = tomlkit.document()
    doc.add(tomlkit.comment("This file is auto-generated by agr. Do not edit."))
    doc.add(tomlkit.nl())
    doc["version"] = lockfile.version

    def _build_aot(entries: list[LockedEntry]) -> tomlkit.items.AoT:
        aot = tomlkit.aot()
        for entry in entries:
            aot.append(entry.to_toml_table())
        return aot

    for key in Lockfile.SECTION_KEYS:
        doc[key] = _build_aot(lockfile._entries(key))
    path.write_text(tomlkit.dumps(doc))
