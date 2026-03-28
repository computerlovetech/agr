"""Tool configuration for AI coding tools.

All tool-specific paths and configuration are isolated in this module.
Supports Claude Code, Cursor, OpenAI Codex, OpenCode,
GitHub Copilot, and Antigravity. All tools use flat naming.
"""

from dataclasses import dataclass
from pathlib import Path

from agr.exceptions import AgrError


@dataclass(frozen=True)
class ToolConfig:
    """Configuration for an AI coding tool."""

    name: str
    config_dir: str  # e.g., ".claude"
    skills_subdir: str = "skills"  # e.g., "skills"
    supports_nested: bool = False  # Reserved for future use
    global_config_dir: str | None = (
        None  # For tools where personal path differs (e.g., Copilot)
    )
    # CLI fields for running skills with the tool
    cli_command: str | None = None  # CLI executable name
    cli_prompt_flag: str | None = "-p"  # Flag to pass prompt (None = positional)
    cli_force_flag: str | None = None  # Flag to skip permission prompts
    cli_continue_flag: str | None = "--continue"  # Flag to continue session
    cli_exec_command: list[str] | None = None  # Command for non-interactive runs
    cli_continue_command: list[str] | None = None  # Command to continue session
    cli_interactive_prompt_positional: bool = (
        False  # Use positional prompt in interactive
    )
    cli_interactive_prompt_flag: str | None = None  # Flag for interactive prompt
    suppress_stderr_non_interactive: bool = False  # Hide streaming output
    skill_prompt_prefix: str = "/"  # Prefix for invoking a skill
    install_hint: str | None = None  # Help text for installation
    detection_signals: tuple[str, ...] = ()  # Paths that indicate tool presence
    instruction_file: str = "AGENTS.md"  # Canonical instruction file for this tool

    def get_skills_dir(self, repo_root: Path) -> Path:
        """Get the skills directory for this tool in a repo."""
        return repo_root / self.config_dir / self.skills_subdir

    def get_global_skills_dir(self) -> Path:
        """Get the global skills directory (in user home)."""
        base = self.global_config_dir or self.config_dir
        return Path.home() / base / self.skills_subdir


# Claude Code tool configuration
# Flat naming: <skill-name>, fallback to user--repo--skill on collision
CLAUDE = ToolConfig(
    name="claude",
    config_dir=".claude",
    cli_command="claude",
    cli_force_flag="--dangerously-skip-permissions",
    cli_interactive_prompt_positional=True,
    install_hint="Install from: https://claude.ai/download",
    detection_signals=(".claude", "CLAUDE.md"),
    instruction_file="CLAUDE.md",
)

# Cursor tool configuration (flat naming: <skill-name>)
# Cursor docs: skill identifiers are "lowercase letters, numbers, and
# hyphens only" and must match the parent folder name.  Primary skill
# directories (.agents/skills/, .cursor/skills/) use flat naming.
CURSOR = ToolConfig(
    name="cursor",
    config_dir=".cursor",
    cli_command="agent",
    # Cursor CLI has no permission-bypass flag (cli_force_flag=None)
    cli_interactive_prompt_positional=True,
    install_hint="Install Cursor IDE to get the agent CLI",
    detection_signals=(".cursor", ".cursorrules"),
)

# OpenAI Codex tool configuration (flat naming: <skill-name>)
# Skill paths based on OpenAI Codex documentation:
# - Project: .agents/skills/
# - Personal: ~/.agents/skills/
CODEX = ToolConfig(
    name="codex",
    config_dir=".agents",
    cli_command="codex",
    cli_prompt_flag=None,  # Codex accepts prompt as positional arg
    cli_force_flag="--full-auto",
    cli_continue_flag=None,
    cli_exec_command=["codex", "exec"],
    cli_continue_command=["codex", "resume", "--last"],
    suppress_stderr_non_interactive=True,
    cli_interactive_prompt_positional=True,
    skill_prompt_prefix="$",
    install_hint="Install OpenAI Codex CLI (npm i -g @openai/codex)",
    detection_signals=(".agents", ".codex"),
)

# OpenCode tool configuration (flat naming: <skill-name>)
# Skill paths based on OpenCode documentation:
# - Project: .opencode/skills/
# - Personal: ~/.config/opencode/skills/
OPENCODE = ToolConfig(
    name="opencode",
    config_dir=".opencode",
    global_config_dir=".config/opencode",
    cli_command="opencode",
    cli_prompt_flag=None,  # opencode run <prompt> (positional arg)
    cli_exec_command=["opencode", "run"],
    cli_interactive_prompt_flag="--prompt",  # opencode --prompt <text> (TUI mode)
    skill_prompt_prefix="",
    install_hint="Install OpenCode CLI (https://opencode.ai/docs/cli/)",
    detection_signals=(".opencode", "opencode.json", "opencode.jsonc"),
)

# GitHub Copilot tool configuration
# Flat naming: <skill-name>, fallback to user--repo--skill on collision
# Skills paths based on: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
# Project: .github/skills/
# Personal: ~/.copilot/skills/ (asymmetric from project path)
COPILOT = ToolConfig(
    name="copilot",
    config_dir=".github",
    global_config_dir=".copilot",  # Personal path differs from project path
    cli_command="copilot",
    cli_force_flag="--allow-all-tools",
    cli_interactive_prompt_flag="-i",
    install_hint="Install GitHub Copilot CLI",
    detection_signals=(
        ".github/copilot",
        ".github/skills",
        ".github/copilot-instructions.md",
        ".github/instructions",
    ),
)

# Antigravity tool configuration (flat naming: <skill-name>)
# Skill paths based on Gemini CLI documentation:
# - Workspace: .gemini/skills/  (primary; .agents/skills/ is an alias)
# - User: ~/.gemini/skills/     (primary; ~/.agents/skills/ is an alias)
# No CLI support — only fields that differ from ToolConfig defaults are set.
ANTIGRAVITY = ToolConfig(
    name="antigravity",
    config_dir=".gemini",
    cli_prompt_flag=None,
    cli_continue_flag=None,
    skill_prompt_prefix="",
    detection_signals=(".gemini", ".agents"),
    instruction_file="GEMINI.md",
)

# All tool configurations — order here determines iteration order in TOOLS.
_ALL_TOOLS: tuple[ToolConfig, ...] = (
    CLAUDE,
    CURSOR,
    CODEX,
    OPENCODE,
    COPILOT,
    ANTIGRAVITY,
)

# Registry of all supported tools, keyed by ToolConfig.name.
TOOLS: dict[str, ToolConfig] = {tool.name: tool for tool in _ALL_TOOLS}

# Default tool names for new configurations
DEFAULT_TOOL_NAMES: tuple[str, ...] = ("claude",)

# Default tool for all operations
DEFAULT_TOOL = CLAUDE


def lookup_skills_dir(
    skills_dirs: dict[str, Path] | None, tool: ToolConfig
) -> Path | None:
    """Look up a tool's explicit skills directory from an optional mapping.

    Returns None when no override exists for the given tool.
    """
    return skills_dirs.get(tool.name) if skills_dirs is not None else None


def build_global_skills_dirs(tools: list[ToolConfig]) -> dict[str, Path]:
    """Build a mapping of tool name to global skills directory.

    Args:
        tools: List of ToolConfig instances

    Returns:
        Dict mapping tool name to its global skills directory path
    """
    return {tool.name: tool.get_global_skills_dir() for tool in tools}


def available_tools_string() -> str:
    """Return a comma-separated string of all supported tool names."""
    return ", ".join(TOOLS.keys())


def get_tool(name: str) -> ToolConfig:
    """Get tool configuration by name.

    Args:
        name: Tool name (e.g., "claude", "cursor")

    Returns:
        ToolConfig for the specified tool

    Raises:
        AgrError: If tool name is not recognized
    """
    if name not in TOOLS:
        raise AgrError(
            f"Unknown tool '{name}'. Available tools: {available_tools_string()}"
        )
    return TOOLS[name]
