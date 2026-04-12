# Security Findings

## SF-001: Symlink-following in skill installation allows local file exfiltration

- **Severity**: High
- **Location**: `agr/_install_common.py:copy_resource_to_destination`, `agr/sdk/cache.py:cache_skill`
- **Description**: `shutil.copytree()` was called with the default `symlinks=False`, which dereferences symlinks and copies the content of the files they point to. A malicious remote skill repository could include symlinks targeting sensitive local files (e.g. `~/.ssh/id_rsa`, `.env`, `~/.aws/credentials`). When a user installs such a skill via `agr add` or `agrx`, the symlinks are dereferenced during the copy, placing the actual file contents into the installed skill directory. Since skills are read by AI agents as context, the sensitive content could then be exposed in agent responses.
- **Resolution**: Fixed. Added `_ignore_symlinks` helper that filters out symlink entries during `shutil.copytree`. Applied to both `copy_resource_to_destination` (main install path) and `cache_skill` (SDK cache path). Added tests confirming that file symlinks and directory symlinks are both skipped during installation.
- **Status**: Fixed (2026-04-12)


## SF-002: Format string injection in source URL template allows Python attribute access

- **Severity**: Medium
- **Location**: `agr/source.py:SourceConfig.build_repo_url`, `agr/config.py:_parse_source_entry`, `agr/commands/config_cmd.py`
- **Description**: `SourceConfig.build_repo_url()` used Python's `str.format()` to interpolate `{owner}` and `{repo}` into the source URL template. Because `str.format()` supports dotted attribute access (e.g. `{owner.__class__.__mro__}`), a malicious `agr.toml` in a cloned repository could craft a `[[source]]` URL template that leaks Python runtime internals. When a user runs `agr sync` or `agr add` against such a project, the format string is evaluated and the resolved attributes are embedded in the git clone URL — potentially exfiltrating runtime metadata to an attacker-controlled server. Additionally, source URLs accepted arbitrary schemes (e.g. `ftp://`, `data:`), which could be abused for protocol-level attacks.
- **Resolution**: Fixed. Replaced `str.format()` with literal `str.replace("{owner}", owner).replace("{repo}", repo)` in `build_repo_url()`, which prevents attribute access, index access, and conversion specifiers. Added URL scheme validation in both `_parse_source_entry()` (TOML loading) and the `config add sources` CLI command, restricting URLs to `https://`, `http://`, `ssh://`, `git://`, `file://`, and absolute paths. Added tests confirming that format string attribute access and conversion specifiers are not evaluated, and that unsupported URL schemes are rejected.
- **Status**: Fixed (2026-04-12)
