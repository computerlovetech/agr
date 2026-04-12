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

    def _entries(self, kind: str = "skill") -> list[LockedEntry]:
        """Return the entries list for a given kind.

        Args:
            kind: ``"skill"``, ``"ralph"``, or ``"package"``.
        """
        if kind == "ralph":
            return self.ralphs
        if kind == "package":
            return self.packages
        return self.skills

    def update_entry(self, entry: LockedEntry, *, kind: str = "skill") -> None:
        """Add or replace an entry by identifier."""
        entries = self._entries(kind)
        entries[:] = [e for e in entries if e.identifier != entry.identifier]
        entries.append(entry)

    def remove_entry(self, identifier: str, *, kind: str = "skill") -> bool:
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
