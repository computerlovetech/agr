"""agr: Agent Resources - Install and manage agent skills."""

from importlib.metadata import version

__version__ = version("agr")

from agr.sdk import Skill, SkillInfo, cache, list_skills, skill_info

__all__ = ["Skill", "SkillInfo", "__version__", "cache", "list_skills", "skill_info"]
