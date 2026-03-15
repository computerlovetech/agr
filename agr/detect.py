"""Tool detection by checking signals defined on each ToolConfig."""

from pathlib import Path

from agr.tool import TOOLS


def detect_tools(repo_root: Path) -> list[str]:
    """Detect tools by checking their detection signals.

    Each tool defines its own detection signals (paths like config
    directories or instruction files). Any single signal is enough
    to detect a tool.

    Args:
        repo_root: Repository root path to check.

    Returns:
        List of detected tool names. Empty list if nothing detected.
    """
    detected: list[str] = []
    for tool in TOOLS.values():
        for signal in tool.detection_signals:
            if (repo_root / signal).exists():
                detected.append(tool.name)
                break
    return detected
