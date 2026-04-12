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


## SF-003: Path traversal in remote handle components allows writes outside skills directory

- **Severity**: High
- **Location**: `agr/handle.py:parse_handle`
- **Description**: Remote handle components (username, repo, skill name) were validated against the reserved `--` separator but not against path traversal sequences `.` and `..`. A handle like `user/repo/..` would parse successfully with `name=".."`, causing the install destination to resolve to `skills_dir / ".."` — the parent of the skills directory. In the worst case (`agr sync --force` or `agr upgrade`), `shutil.rmtree()` would delete the parent directory before `shutil.copytree()` replaces it with skill contents. This is especially dangerous through the **package expansion** path (`package.py:expand_packages`): a malicious remote package could include a sub-dependency with a traversal handle in its `agr.toml`, and the user would never see the raw handle — they'd only have a top-level `type = "package"` dependency. The same issue applied to `.` as a component, which would resolve the destination to the skills directory itself. Local handles were already protected (`.` produces an empty name caught by `not name`, `..` is explicitly rejected), but the remote handle branch had no such checks.
- **Resolution**: Fixed. Added `_validate_no_path_traversal()` helper in `handle.py` that rejects `.` and `..` as handle components. Applied to all remote handle parsing branches (1-part with default_owner, 2-part user/skill, 3-part user/repo/skill) alongside the existing `_validate_no_separator()` check. Added 8 tests covering traversal in each component position and both `.` and `..` variants.
- **Status**: Fixed (2026-04-12)


## SF-004: Lockfile commit field accepts arbitrary git refs, defeating --frozen immutability

- **Severity**: Medium
- **Location**: `agr/git.py:fetch_and_checkout_commit`, `agr/lockfile.py:LockedEntry.from_dict`
- **Description**: The lockfile's `commit` field was loaded from disk as an arbitrary string with no format validation. In `--frozen` mode, `fetch_and_checkout_commit()` passed this string directly to `git fetch --depth=1 origin <commit>` and `git checkout <commit>`. While agr always writes valid 40-character hex SHAs when generating the lockfile, a tampered lockfile (e.g. via a malicious pull request that modifies `agr.lock`) could substitute a branch name (`main`), tag (`v1.0`), or other git ref for a pinned commit SHA. When another developer then runs `agr sync --frozen`, git would resolve the ref to whatever commit it points to at that moment — potentially a different (malicious) commit than the one originally pinned. This defeats the core purpose of `--frozen` mode: ensuring reproducible, immutable installs from exact commit SHAs. The attack is particularly effective because lockfile diffs are often large and reviewers tend to skim them.
- **Resolution**: Fixed. Added `validate_commit_sha()` function in `git.py` with a regex check (`^[0-9a-f]{40}$`) that rejects anything other than a full 40-character lowercase hex SHA. Called at the top of `fetch_and_checkout_commit()` before any git operations. Added 11 tests covering valid SHAs, branch names, tags, short SHAs, uppercase hex, empty strings, oversized strings, and ref paths.
- **Status**: Fixed (2026-04-12)
