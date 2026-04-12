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


## SF-005: GitHub token exposed in process command-line arguments via URL embedding

- **Severity**: Medium
- **Location**: `agr/git.py:_apply_github_token`, `agr/git.py:downloaded_repo`
- **Description**: `_apply_github_token()` embedded the GitHub token directly into the git clone URL (e.g. `https://TOKEN:x-oauth-basic@github.com/owner/repo.git`). This URL was passed as a command-line argument to `git clone` and `git ls-remote` via `subprocess.run()`. On Linux, command-line arguments are world-readable via `/proc/PID/cmdline`; on macOS, they are visible to all users via `ps aux`. Any user or process on the same machine could observe the token during the (brief) git operation window. This is especially concerning on shared CI/CD runners, multi-user development servers, and environments with process monitoring. Although the token exposure window is short (the lifetime of the git subprocess), automated process scanners or audit logging could capture it persistently.
- **Resolution**: Fixed. Added `_build_github_auth_env()` function that passes the GitHub token via `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_N`/`GIT_CONFIG_VALUE_N` environment variables (git 2.31+). These env vars configure `http.https://github.com/.extraheader` with an `AUTHORIZATION: bearer` header, scoped to github.com only. The `_run_git()` function now automatically merges the auth env into every git subprocess call. Environment variables are only readable by the owning user (unlike cmdline which is world-readable), and the URL-scoped `http.extraheader` ensures the token is never sent to non-GitHub hosts. The function also correctly appends to any existing `GIT_CONFIG_COUNT` entries. Added 7 tests covering token presence in env values, absence from keys, env count appending, GH_TOKEN fallback, empty token handling, and github.com scoping.
- **Status**: Fixed (2026-04-12)


## SF-006: Remote packages can inject local path dependencies to read arbitrary directories

- **Severity**: High
- **Location**: `agr/package.py:expand_packages`
- **Description**: `expand_packages()` rejected local *packages* (`type = "package"` with a `path` field) but silently accepted local *skill/ralph* sub-dependencies from remote packages. A malicious remote package could include `{path = "../../.env", type = "skill"}` in its `agr.toml`. During `agr sync` or `agr add`, the package expansion would add this local path dependency to the flat list. When later installed, the path resolves relative to the user's `repo_root`, causing the contents of arbitrary directories to be copied into the skills directory where AI agents read them. The attack is especially effective because package sub-dependencies are expanded transparently — the user only sees a top-level `type = "package"` entry in their `agr.toml` and never reviews the transitive local paths. A nested package chain (package A depends on package B which contains the malicious local dep) further obscures the attack.
- **Resolution**: Fixed. Added a check at the top of the sub-dependency loop in `expand_packages()` that rejects any local path dependency (`sub_dep.is_local`) found in a remote package's sub-manifest, raising `ConfigError` with a message naming both the offending path and the parent package. This applies to all dependency types (skills, ralphs, and nested packages). Added 5 tests covering: local skill paths, local ralph paths, traversal paths, nested package chains with local deps, and error message content verification.
- **Status**: Fixed (2026-04-12)
