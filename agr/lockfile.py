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

    def _entries(self, ralph: bool) -> list[LockedEntry]:
        """Return the skill or ralph entries list."""
        return self.ralphs if ralph else self.skills

    def _set_entries(self, entries: list[LockedEntry], ralph: bool) -> None:
        """Replace the skill or ralph entries list."""
        if ralph:
            self.ralphs = entries
        else:
            self.skills = entries

    def update_entry(self, entry: LockedEntry, *, ralph: bool = False) -> None:
        """Add or replace an entry by identifier."""
        filtered = [e for e in self._entries(ralph) if e.identifier != entry.identifier]
        filtered.append(entry)
        self._set_entries(filtered, ralph)

    def remove_entry(self, identifier: str, *, ralph: bool = False) -> bool:
        """Remove an entry by identifier.

        Returns True if an entry was removed, False if no match was found.
        """
        entries = self._entries(ralph)
        filtered = [e for e in entries if e.identifier != identifier]
        self._set_entries(filtered, ralph)
        return len(filtered) < len(entries)

    def find_entry(self, dep: Dependency) -> LockedEntry | None:
        """Look up a dependency's entry."""
        identifier = dep.identifier
        ralph = dep.is_ralph
        for entry in self._entries(ralph):
            if entry.identifier == identifier:
                return entry
        return None

    def is_current(self, dependencies: list[Dependency]) -> bool:
        """Check if the lockfile covers exactly the same deps as agr.toml.

        Returns True only if the lockfile has entries for all dependencies
        and no extra entries. Does not check whether SHAs are stale.
        """
        lockfile_skill_ids = {s.identifier for s in self.skills}
        lockfile_ralph_ids = {r.identifier for r in self.ralphs}
        config_skill_ids = {d.identifier for d in dependencies if not d.is_ralph}
        config_ralph_ids = {d.identifier for d in dependencies if d.is_ralph}
        return (
            lockfile_skill_ids == config_skill_ids
            and lockfile_ralph_ids == config_ralph_ids
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

    return Lockfile(version=version, skills=skills, ralphs=ralphs)


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
    path.write_text(tomlkit.dumps(doc))
