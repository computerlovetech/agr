"""Tool configuration for AI coding tools.

All tool-specific paths and configuration are isolated in this module.
Supports Claude Code (flat naming), OpenAI Codex (flat naming),
Cursor (nested directories), OpenCode (flat naming),
GitHub Copilot (flat naming), and Antigravity (flat naming).
"""

from dataclasses import dataclass
from pathlib import Path

from agr.exceptions import AgrError


@dataclass(frozen=True)
class ToolConfig:
    """Configuration for an AI coding tool."""

    name: str
    config_dir: str  # e.g., ".claude"
    skills_subdir: str  # e.g., "skills"
    supports_nested: bool = False  # True for nested dir structure (Cursor)
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
    skills_subdir="skills",
    supports_nested=False,
    cli_command="claude",
    cli_prompt_flag="-p",
    cli_force_flag="--dangerously-skip-permissions",
    cli_continue_flag="--continue",
    cli_interactive_prompt_positional=True,
    install_hint="Install from: https://claude.ai/download",
    detection_signals=(".claude", "CLAUDE.md"),
    instruction_file="CLAUDE.md",
)

# Cursor tool configuration (nested dirs: maragudk/skills/bluesky/)
CURSOR = ToolConfig(
    name="cursor",
    config_dir=".cursor",
    skills_subdir="skills",
    supports_nested=True,
    cli_command="agent",
    cli_prompt_flag="-p",
    cli_force_flag="--force",
    cli_continue_flag="--continue",
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
    skills_subdir="skills",
    supports_nested=False,
    cli_command="codex",
    cli_prompt_flag=None,  # Codex accepts prompt as positional arg
    cli_force_flag=None,
    cli_continue_flag=None,
    cli_exec_command=["codex", "exec"],
    cli_continue_command=["codex", "resume", "--last"],
    suppress_stderr_non_interactive=True,
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
    skills_subdir="skills",
    supports_nested=False,
    global_config_dir=".config/opencode",
    cli_command="opencode",
    cli_prompt_flag=None,  # opencode run accepts prompt as positional args
    cli_continue_flag="--continue",
    cli_exec_command=["opencode", "run"],
    cli_interactive_prompt_flag="--prompt",
    skill_prompt_prefix="",
    install_hint="Install OpenCode CLI (https://opencode.ai/docs/cli/)",
    detection_signals=(".opencode",),
)

# GitHub Copilot tool configuration
# Flat naming: <skill-name>, fallback to user--repo--skill on collision
# Skills paths based on: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
# Project: .github/skills/
# Personal: ~/.copilot/skills/ (asymmetric from project path)
COPILOT = ToolConfig(
    name="copilot",
    config_dir=".github",
    skills_subdir="skills",
    supports_nested=False,  # Flat naming like Claude
    global_config_dir=".copilot",  # Personal path differs from project path
    cli_command="copilot",
    cli_prompt_flag="-p",
    cli_force_flag="--allow-all-tools",
    cli_continue_flag="--continue",
    cli_interactive_prompt_flag="-i",
    install_hint="Install GitHub Copilot CLI",
    detection_signals=(".github/copilot", ".github/skills"),
)

# Antigravity tool configuration (flat naming: <skill-name>)
# Skill paths based on Antigravity documentation:
# - Workspace: .agent/skills/
# - Global: ~/.gemini/antigravity/skills/
ANTIGRAVITY = ToolConfig(
    name="antigravity",
    config_dir=".agent",
    skills_subdir="skills",
    supports_nested=False,
    global_config_dir=".gemini/antigravity",
    cli_command=None,
    cli_prompt_flag=None,
    cli_force_flag=None,
    cli_continue_flag=None,
    cli_exec_command=None,
    cli_continue_command=None,
    cli_interactive_prompt_positional=False,
    cli_interactive_prompt_flag=None,
    suppress_stderr_non_interactive=False,
    skill_prompt_prefix="",
    install_hint=None,
    detection_signals=(".agent",),
    instruction_file="GEMINI.md",
)

# Registry of all supported tools
TOOLS: dict[str, ToolConfig] = {
    "claude": CLAUDE,
    "cursor": CURSOR,
    "codex": CODEX,
    "opencode": OPENCODE,
    "copilot": COPILOT,
    "antigravity": ANTIGRAVITY,
}

# Default tool names for new configurations
DEFAULT_TOOL_NAMES: list[str] = ["claude"]

# Default tool for all operations
DEFAULT_TOOL = CLAUDE


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
