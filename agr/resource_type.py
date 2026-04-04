"""Resource type abstraction for skills and ralphs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceType:
    """Parameterises shared logic across resource kinds (skills, ralphs).

    Attributes:
        marker: Filename that identifies a directory as this resource type
                (e.g. ``"SKILL.md"`` or ``"RALPH.md"``).
        name: Human-readable singular name (``"skill"`` or ``"ralph"``).
        has_tool_field: Whether installations are per-tool (skills) or
                        project-level (ralphs).
    """

    marker: str
    name: str
    has_tool_field: bool


SKILL_RESOURCE = ResourceType(marker="SKILL.md", name="skill", has_tool_field=True)
RALPH_RESOURCE = ResourceType(marker="RALPH.md", name="ralph", has_tool_field=False)
