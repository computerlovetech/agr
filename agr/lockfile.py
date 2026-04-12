"""Lockfile management for reproducible skill installs.

The lockfile (agr.lock) pins exact git commit SHAs for every resolved
dependency so that ``agr sync`` produces identical results across
machines and over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import tomlkit
import tomlkit.items
from tomlkit import TOMLDocument
from tomlkit.exceptions import TOMLKitError

from agr.config import Dependency
from agr.exceptions import ConfigError

LOCKFILE_FILENAME = "agr.lock"
LOCKFILE_VERSION = 1


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
        ("parent", "parent"),
    )

    @property
    def is_local(self) -> bool:
        return self.path is not None

    @property
    def identifier(self) -> str:
        """Unique identifier matching Dependency.identifier."""
        return self.path or self.handle or ""

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
        return cls(
            installed_name=str(data.get(cls._TOML_KEY_INSTALLED_NAME, "")),
            **kwargs,
        )

    def to_toml_table(self) -> tomlkit.items.Table:
        """Serialize this entry into a tomlkit Table."""
        table = tomlkit.table()
        for attr, key in self._TOML_OPTIONAL_FIELDS:
            value = getattr(self, attr)
            if value is not None:
                table[key] = value
        table[self._TOML_KEY_INSTALLED_NAME] = self.installed_name
        return table


@dataclass
class Lockfile:
    """The full lockfile state."""

    version: int = LOCKFILE_VERSION
    skills: list[LockedEntry] = field(default_factory=list)
    ralphs: list[LockedEntry] = field(default_factory=list)
    packages: list[LockedEntry] = field(default_factory=list)

    def _entries(
        self, ralph: bool = False, kind: str | None = None
    ) -> list[LockedEntry]:
        """Return the entries list for a given kind.

        The ``kind`` parameter accepts ``"skill"``, ``"ralph"``, or
        ``"package"``.  When omitted, the legacy ``ralph`` bool is used
        for backward compatibility.
        """
        if kind is not None:
            if kind == "ralph":
                return self.ralphs
            if kind == "package":
                return self.packages
            return self.skills
        return self.ralphs if ralph else self.skills

    def _set_entries(
        self, entries: list[LockedEntry], ralph: bool = False, kind: str | None = None
    ) -> None:
        """Replace the entries list for a given kind."""
        if kind is not None:
            if kind == "ralph":
                self.ralphs = entries
            elif kind == "package":
                self.packages = entries
            else:
                self.skills = entries
            return
        if ralph:
            self.ralphs = entries
        else:
            self.skills = entries

    def update_entry(
        self, entry: LockedEntry, *, ralph: bool = False, kind: str | None = None
    ) -> None:
        """Add or replace an entry by identifier."""
        filtered = [
            e
            for e in self._entries(ralph, kind=kind)
            if e.identifier != entry.identifier
        ]
        filtered.append(entry)
        self._set_entries(filtered, ralph, kind=kind)

    def remove_entry(
        self, identifier: str, *, ralph: bool = False, kind: str | None = None
    ) -> bool:
        """Remove an entry by identifier.

        Returns True if an entry was removed, False if no match was found.
        """
        entries = self._entries(ralph, kind=kind)
        filtered = [e for e in entries if e.identifier != identifier]
        self._set_entries(filtered, ralph, kind=kind)
        return len(filtered) < len(entries)

    def find_entry(
        self, dep: Dependency, *, kind: str | None = None
    ) -> LockedEntry | None:
        """Look up a dependency's entry."""
        identifier = dep.identifier
        if kind is None:
            if dep.is_package:
                kind = "package"
            elif dep.is_ralph:
                kind = "ralph"
            else:
                kind = "skill"
        for entry in self._entries(kind=kind):
            if entry.identifier == identifier:
                return entry
        return None

    def is_current(self, dependencies: list[Dependency]) -> bool:
        """Check if the lockfile covers exactly the same deps as agr.toml.

        Returns True only if the lockfile has entries for all dependencies
        and no extra entries. Does not check whether SHAs are stale.

        Transitive entries (those with a ``parent`` field) are excluded
        from the comparison because they originate from package expansion
        at sync time and are not listed in agr.toml directly.
        """
        lockfile_skill_ids = {s.identifier for s in self.skills if not s.parent}
        lockfile_ralph_ids = {r.identifier for r in self.ralphs if not r.parent}
        lockfile_pkg_ids = {p.identifier for p in self.packages if not p.parent}
        config_skill_ids = {d.identifier for d in dependencies if d.is_skill}
        config_ralph_ids = {d.identifier for d in dependencies if d.is_ralph}
        config_pkg_ids = {d.identifier for d in dependencies if d.is_package}
        return (
            lockfile_skill_ids == config_skill_ids
            and lockfile_ralph_ids == config_ralph_ids
            and lockfile_pkg_ids == config_pkg_ids
        )


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

    skills = _parse_locked_entries(doc, "skill")
    ralphs = _parse_locked_entries(doc, "ralph")
    packages = _parse_locked_entries(doc, "package")

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

    doc["skill"] = _build_aot(lockfile.skills)
    doc["ralph"] = _build_aot(lockfile.ralphs)
    doc["package"] = _build_aot(lockfile.packages)
    path.write_text(tomlkit.dumps(doc))
