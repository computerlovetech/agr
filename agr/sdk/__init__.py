"""SDK for programmatic access to agent resources.

This module provides a HuggingFace-style API for loading skills from Git repositories.

Example:
    >>> from agr import Skill
    >>> skill = Skill.from_git("kasperjunge/commit")
    >>> print(skill.prompt)  # Contents of SKILL.md
    >>> print(skill.files)   # List of files

    >>> from agr import list_skills, skill_info
    >>> skills = list_skills("anthropics/skills")
    >>> info = skill_info("anthropics/skills/code-review")
"""

from agr.sdk.cache import cache
from agr.sdk.hub import list_skills, skill_info
from agr.sdk.skill import Skill
from agr.sdk.types import SkillInfo

__all__ = ["Skill", "SkillInfo", "cache", "list_skills", "skill_info"]
