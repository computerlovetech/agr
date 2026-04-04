"""Skill and ralph installation, uninstallation, and query operations.

This module re-exports the public API from focused sub-modules for
backward compatibility.  New code should import directly from
agr.skill_installer, agr.ralph_installer, or agr._install_common.
"""

from agr._install_common import (  # noqa: F401
    InstallResult,
    _cleanup_empty_parents,
)
from agr.skill_installer import (  # noqa: F401
    fetch_and_install,
    fetch_and_install_to_tools,
    filter_tools_needing_install,
    install_local_skill,
    install_remote_skill,
    install_skill_from_repo,
    install_skill_from_repo_to_tools,
    is_skill_installed,
    list_remote_repo_skills,
    prepare_repo_for_skill,
    prepare_repo_for_skills,
    skill_not_found_message,
    uninstall_skill,
)
from agr.ralph_installer import (  # noqa: F401
    fetch_and_install_ralph,
    get_ralphs_dir,
    install_local_ralph,
    install_ralph_from_repo,
    is_ralph_installed,
    prepare_repo_for_ralph,
    prepare_repo_for_ralphs,
    ralph_not_found_message,
    uninstall_ralph,
)

__all__ = [
    "InstallResult",
    "fetch_and_install",
    "fetch_and_install_ralph",
    "fetch_and_install_to_tools",
    "filter_tools_needing_install",
    "get_ralphs_dir",
    "install_local_ralph",
    "install_local_skill",
    "install_ralph_from_repo",
    "install_remote_skill",
    "install_skill_from_repo",
    "install_skill_from_repo_to_tools",
    "is_ralph_installed",
    "is_skill_installed",
    "list_remote_repo_skills",
    "prepare_repo_for_skill",
    "prepare_repo_for_skills",
    "ralph_not_found_message",
    "skill_not_found_message",
    "uninstall_ralph",
    "uninstall_skill",
    "_cleanup_empty_parents",
]
