# Security Findings

## SF-001: Symlink-following in skill installation allows local file exfiltration

- **Severity**: High
- **Location**: `agr/_install_common.py:copy_resource_to_destination`, `agr/sdk/cache.py:cache_skill`
- **Description**: `shutil.copytree()` was called with the default `symlinks=False`, which dereferences symlinks and copies the content of the files they point to. A malicious remote skill repository could include symlinks targeting sensitive local files (e.g. `~/.ssh/id_rsa`, `.env`, `~/.aws/credentials`). When a user installs such a skill via `agr add` or `agrx`, the symlinks are dereferenced during the copy, placing the actual file contents into the installed skill directory. Since skills are read by AI agents as context, the sensitive content could then be exposed in agent responses.
- **Resolution**: Fixed. Added `_ignore_symlinks` helper that filters out symlink entries during `shutil.copytree`. Applied to both `copy_resource_to_destination` (main install path) and `cache_skill` (SDK cache path). Added tests confirming that file symlinks and directory symlinks are both skipped during installation.
- **Status**: Fixed (2026-04-12)
