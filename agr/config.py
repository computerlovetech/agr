"""Configuration management for agr.toml."""

from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Generator
from typing import Any

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.exceptions import TOMLKitError

from agr.console import error_exit
from agr.exceptions import ConfigError
from agr.handle import ParsedHandle, parse_handle
from agr.instructions import INSTRUCTION_FILES
from agr.source import (
    DEFAULT_SOURCE_NAME,
    SOURCE_TYPE_GIT,
    SourceConfig,
    SourceResolver,
    default_sources,
)
from agr.tool import (
    DEFAULT_TOOL_NAMES,
    TOOLS,
    ToolConfig,
    available_tools_string,
    get_tool,
)

CONFIG_FILENAME = "agr.toml"
DEPENDENCY_TYPE_SKILL = "skill"


def validate_canonical_instructions(value: str) -> None:
    """Raise ConfigError if *value* is not a valid canonical instructions file."""
    if value not in INSTRUCTION_FILES:
        valid = ", ".join(f"'{v}'" for v in sorted(INSTRUCTION_FILES))
        raise ConfigError(f"canonical_instructions must be one of: {valid}")


def _validate_default_source(
    default_source: str, sources: list[SourceConfig]
) -> None:
    """Raise ConfigError if *default_source* is not in the sources list."""
    if not any(source.name == default_source for source in sources):
        raise ConfigError(
            f"default_source '{default_source}' not found in [[source]] list"
        )


def _parse_tools_from_doc(doc: TOMLDocument) -> list[str]:
    """Parse and validate tools list from TOML document."""
    tools_list = doc.get("tools", list(DEFAULT_TOOL_NAMES))
    if isinstance(tools_list, list):
        tools = [str(t) for t in tools_list]
    else:
        tools = list(DEFAULT_TOOL_NAMES)

    for tool_name in tools:
        if tool_name not in TOOLS:
            raise ConfigError(
                f"Unknown tool '{tool_name}' in agr.toml. "
                f"Available: {available_tools_string()}"
            )
    return tools


def _parse_default_tool_from_doc(doc: TOMLDocument, tools: list[str]) -> str | None:
    """Parse and validate default_tool from TOML document."""
    default_tool = doc.get("default_tool")
    if default_tool is None:
        return None
    default_tool = str(default_tool)
    if not default_tool:
        return None
    if default_tool not in TOOLS:
        raise ConfigError(
            f"Unknown default_tool '{default_tool}' "
            f"in agr.toml. Available: "
            f"{available_tools_string()}"
        )
    if default_tool not in tools:
        raise ConfigError("default_tool must be listed in tools in agr.toml")
    return default_tool


def _parse_source_entry(item: Any) -> SourceConfig:
    """Parse and validate a single ``[[source]]`` entry.

    Args:
        item: A TOML table (dict) representing one ``[[source]]`` block.

    Returns:
        A validated SourceConfig.

    Raises:
        ConfigError: If the entry is malformed or has invalid values.
    """
    if not isinstance(item, dict):
        raise ConfigError("Invalid [[source]] entry in agr.toml")
    name = str(item.get("name", "")).strip()
    source_type = str(item.get("type", SOURCE_TYPE_GIT)).strip()
    url = item.get("url")
    if not name:
        raise ConfigError("Source entry missing name")
    if source_type != SOURCE_TYPE_GIT:
        raise ConfigError(
            f"Unsupported source type '{source_type}' for '{name}'"
        )
    if not url:
        raise ConfigError(f"Source '{name}' missing url")
    return SourceConfig(name=name, type=source_type, url=str(url))


def _parse_sources_from_doc(
    doc: TOMLDocument,
) -> tuple[list[SourceConfig], str]:
    """Parse sources and default_source from TOML document.

    Returns:
        Tuple of (sources list, default_source name).
    """
    sources_list = doc.get("source")
    sources: list[SourceConfig] = []
    if sources_list is None:
        sources = default_sources()
    else:
        if not isinstance(sources_list, list):
            raise ConfigError("Invalid [[source]] format in agr.toml")
        sources = [_parse_source_entry(item) for item in sources_list]

    default_source = doc.get("default_source")
    if default_source:
        default_source = str(default_source)
    elif sources:
        default_source = sources[0].name
    else:
        default_source = DEFAULT_SOURCE_NAME

    _validate_default_source(default_source, sources)

    return sources, default_source


@dataclass
class Dependency:
    """A dependency in agr.toml.

    Examples:
        Remote: { handle = "kasperjunge/commit", type = "skill" }
        Local:  { path = "./my-skill", type = "skill" }
    """

    type: str  # Always "skill" for now
    handle: str | None = None  # Remote Git reference
    path: str | None = None  # Local path
    source: str | None = None  # Optional source name for remote handles

    def __post_init__(self) -> None:
        """Validate dependency has exactly one source."""
        if self.handle and self.path:
            raise ValueError("Dependency cannot have both handle and path")
        if not self.handle and not self.path:
            raise ValueError("Dependency must have either handle or path")
        if self.path and self.source:
            raise ValueError("Local dependency cannot specify a source")

    @property
    def is_local(self) -> bool:
        """True if this is a local path dependency."""
        return self.path is not None

    @property
    def is_remote(self) -> bool:
        """True if this is a remote GitHub dependency."""
        return self.handle is not None

    @property
    def identifier(self) -> str:
        """Unique identifier (path or handle)."""
        return self.path or self.handle or ""

    def to_parsed_handle(self) -> ParsedHandle:
        """Parse this dependency's reference into a ParsedHandle."""
        ref = self.path or self.handle or ""
        if self.is_local:
            path = Path(ref)
            return ParsedHandle(is_local=True, name=path.name, local_path=path)
        return parse_handle(ref, prefer_local=False)

    def resolve_source_name(self, default_source: str | None = None) -> str | None:
        """Get the effective source name for this dependency.

        Returns None for local dependencies, otherwise the explicit
        source or the provided default.
        """
        if self.is_local:
            return None
        return self.source or default_source

    def resolve(
        self, default_source: str | None = None
    ) -> tuple[ParsedHandle, str | None]:
        """Parse the handle and resolve the source name in one step.

        Combines ``to_parsed_handle()`` and ``resolve_source_name()`` —
        the two calls are always used together when processing dependencies.
        """
        return self.to_parsed_handle(), self.resolve_source_name(default_source)


def _parse_dependencies_from_doc(
    doc: TOMLDocument,
    source_names: set[str],
) -> list[Dependency]:
    """Parse and validate dependencies from TOML document."""
    sources_list = doc.get("source")
    deps_list = doc.get("dependencies", [])
    if "dependencies" not in doc and sources_list:
        for item in sources_list:
            if isinstance(item, dict) and "dependencies" in item:
                raise ConfigError(
                    "dependencies must be declared before [[source]] blocks"
                )

    dependencies: list[Dependency] = []
    for item in deps_list:
        if not isinstance(item, dict):
            continue
        dep_type = item.get("type", DEPENDENCY_TYPE_SKILL)
        handle = item.get("handle")
        path_val = item.get("path")
        source = item.get("source")
        if source is not None:
            source = str(source)

        if handle or path_val:
            try:
                dependencies.append(
                    Dependency(
                        handle=handle, path=path_val, type=dep_type, source=source
                    )
                )
            except ValueError as e:
                raise ConfigError(str(e)) from None

    for dep in dependencies:
        if dep.source and dep.source not in source_names:
            raise ConfigError(
                f"Unknown source '{dep.source}' in dependency '{dep.identifier}'"
            )

    return dependencies


@dataclass
class AgrConfig:
    """Configuration loaded from agr.toml.

    Format:
        default_source = "github"

        [[source]]
        name = "github"
        type = "git"
        url = "https://github.com/{owner}/{repo}.git"

        tools = ["claude", "cursor"]  # Optional, defaults to ["claude"]
        default_tool = "claude"  # Optional, overrides first tool
        sync_instructions = true  # Optional
        canonical_instructions = "CLAUDE.md"  # Optional
        dependencies = [
            { handle = "kasperjunge/commit", type = "skill" },
            { path = "./my-skill", type = "skill" },
        ]
    """

    dependencies: list[Dependency] = field(default_factory=list)
    tools: list[str] = field(default_factory=lambda: list(DEFAULT_TOOL_NAMES))
    sources: list[SourceConfig] = field(default_factory=default_sources)
    default_source: str = DEFAULT_SOURCE_NAME
    default_tool: str | None = None
    sync_instructions: bool | None = None
    canonical_instructions: str | None = None
    _path: Path | None = field(default=None, repr=False)

    def get_tools(self) -> list[ToolConfig]:
        """Get ToolConfig instances for configured tools.

        Returns:
            List of ToolConfig instances

        Raises:
            AgrError: If any tool name is not recognized
        """
        return [get_tool(t) for t in self.tools]

    def get_source_resolver(self) -> SourceResolver:
        """Get a SourceResolver for this config."""
        return SourceResolver(self.sources, self.default_source)

    @classmethod
    def load(cls, path: Path) -> "AgrConfig":
        """Load configuration from agr.toml.

        Args:
            path: Path to agr.toml

        Returns:
            AgrConfig instance

        Raises:
            ConfigError: If the file contains invalid TOML
        """
        if not path.exists():
            config = cls()
            config._path = path
            return config

        try:
            content = path.read_text()
            doc = tomlkit.parse(content)
        except TOMLKitError as e:
            raise ConfigError(f"Invalid TOML in {path}: {e}") from e

        config = cls()
        config._path = path

        config.tools = _parse_tools_from_doc(doc)
        config.default_tool = _parse_default_tool_from_doc(doc, config.tools)

        sync_instructions = doc.get("sync_instructions")
        if sync_instructions is not None:
            config.sync_instructions = bool(sync_instructions)

        canonical_instructions = doc.get("canonical_instructions")
        if canonical_instructions is not None:
            canonical_instructions = str(canonical_instructions)
            validate_canonical_instructions(canonical_instructions)
            config.canonical_instructions = canonical_instructions

        config.sources, config.default_source = _parse_sources_from_doc(doc)
        source_names = {s.name for s in config.sources}
        config.dependencies = _parse_dependencies_from_doc(doc, source_names)

        return config

    def save(self, path: Path | None = None) -> None:
        """Save configuration to agr.toml.

        Args:
            path: Path to save to (uses original path if not specified)

        Raises:
            ValueError: If no path specified and no original path
        """
        save_path = path or self._path
        if save_path is None:
            raise ValueError("No path specified for saving config")

        doc: TOMLDocument = tomlkit.document()

        # Always write default source and sources for clarity
        default_source = self.default_source or DEFAULT_SOURCE_NAME
        sources = self.sources or default_sources()
        _validate_default_source(default_source, sources)
        doc["default_source"] = default_source

        # Save tools array if not default
        if self.tools != list(DEFAULT_TOOL_NAMES):
            tools_array = tomlkit.array()
            for tool in self.tools:
                tools_array.append(tool)
            doc["tools"] = tools_array

        if self.default_tool:
            if self.default_tool not in self.tools:
                raise ValueError("default_tool must be listed in tools")
            doc["default_tool"] = self.default_tool

        if self.sync_instructions is not None:
            doc["sync_instructions"] = bool(self.sync_instructions)

        if self.canonical_instructions:
            doc["canonical_instructions"] = self.canonical_instructions

        # Build dependencies array
        deps_array = tomlkit.array()
        deps_array.multiline(True)

        for dep in self.dependencies:
            item = tomlkit.inline_table()
            if dep.handle:
                item["handle"] = dep.handle
            if dep.path:
                item["path"] = dep.path
            if dep.source:
                item["source"] = dep.source
            item["type"] = dep.type
            deps_array.append(item)

        doc["dependencies"] = deps_array
        sources_array = tomlkit.aot()
        for source in sources:
            table = tomlkit.table()
            table["name"] = source.name
            table["type"] = source.type
            table["url"] = source.url
            sources_array.append(table)
        doc["source"] = sources_array
        save_path.write_text(tomlkit.dumps(doc))
        self._path = save_path

    def add_dependency(self, dep: Dependency) -> None:
        """Add or update a dependency.

        If a dependency with the same identifier exists, it's replaced.
        """
        self.dependencies = [
            d for d in self.dependencies if d.identifier != dep.identifier
        ]
        self.dependencies.append(dep)

    def remove_dependency(self, identifier: str) -> bool:
        """Remove a dependency by identifier (handle or path).

        Returns:
            True if removed, False if not found
        """
        original_len = len(self.dependencies)
        self.dependencies = [d for d in self.dependencies if d.identifier != identifier]
        return len(self.dependencies) < original_len

    def get_by_identifier(self, identifier: str) -> Dependency | None:
        """Find a dependency by handle or path."""
        for dep in self.dependencies:
            if dep.identifier == identifier:
                return dep
        return None


def _walk_ancestors(start_path: Path | None = None) -> Generator[Path, None, None]:
    """Yield directories from start_path up to the filesystem root.

    Args:
        start_path: Directory to start from (defaults to cwd)

    Yields:
        Each ancestor directory, starting with start_path itself.
    """
    current = start_path or Path.cwd()
    while True:
        yield current
        parent = current.parent
        if parent == current:
            return
        current = parent


def find_config(start_path: Path | None = None) -> Path | None:
    """Find agr.toml by walking up from start path.

    Stops at git root or filesystem root.

    Args:
        start_path: Directory to start searching from (defaults to cwd)

    Returns:
        Path to agr.toml if found, None otherwise
    """
    for directory in _walk_ancestors(start_path):
        config_path = directory / CONFIG_FILENAME
        if config_path.exists():
            return config_path
        if (directory / ".git").exists():
            return None
    return None


def find_repo_root(start_path: Path | None = None) -> Path | None:
    """Find the git repository root.

    Args:
        start_path: Directory to start searching from (defaults to cwd)

    Returns:
        Path to repo root if found, None otherwise
    """
    for directory in _walk_ancestors(start_path):
        if (directory / ".git").exists():
            return directory
    return None


def require_repo_root(start_path: Path | None = None) -> Path:
    """Find the git repository root or exit with an error.

    Like ``find_repo_root``, but prints an error message and raises
    ``SystemExit(1)`` when no git repository is found.

    Args:
        start_path: Directory to start searching from (defaults to cwd)

    Returns:
        Path to repo root

    Raises:
        SystemExit: If not inside a git repository
    """
    repo_root = find_repo_root(start_path)
    if repo_root is None:
        error_exit("Not in a git repository")
    return repo_root


def require_config(start_path: Path | None = None) -> Path:
    """Find agr.toml or exit with a user-facing error.

    Like ``find_config``, but prints an error message and raises
    ``SystemExit(1)`` when no config file is found.

    Args:
        start_path: Directory to start searching from (defaults to cwd)

    Returns:
        Path to config file

    Raises:
        SystemExit: If no agr.toml is found
    """
    config_path = find_config(start_path)
    if config_path is None:
        error_exit("No agr.toml found.", hint="Run 'agr init' first to create one.")
    return config_path


def get_global_config_dir() -> Path:
    """Get global agr config directory (~/.agr)."""
    return Path.home() / ".agr"


def get_global_config_path() -> Path:
    """Get global agr config path (~/.agr/agr.toml)."""
    return get_global_config_dir() / CONFIG_FILENAME


def get_or_create_global_config() -> tuple[Path, AgrConfig]:
    """Get existing global config or create one with defaults."""
    config_path = get_global_config_path()
    if config_path.exists():
        return config_path, AgrConfig.load(config_path)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = AgrConfig()
    config.save(config_path)
    return config_path, config
