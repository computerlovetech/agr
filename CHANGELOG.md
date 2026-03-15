# Changelog

## [Unreleased]

## [0.7.10] - 2026-03-10
### Changed
- Codex skills directory from `.codex/skills/` to `.agents/skills/` (following Codex upstream change)
- OpenCode skills directory from `.opencode/skill/` to `.opencode/skills/` (following OpenCode upstream change)

### Added
- Auto-migration from `.codex/skills/` to `.agents/skills/` during `agr sync`
- Auto-migration from `.opencode/skill/` to `.opencode/skills/` during `agr sync`, `agr add`, and `agr remove`
- Backwards-compatible detection of both `.agents/` and `.codex/` for Codex


## [0.7.9] - 2026-03-05

### Added
- Deterministic content hashes for installed skills (`sha256:` prefixed)
- `compute_content_hash()` in `agr/metadata.py` for SHA-256 hashing of skill directory contents
- `content_hash` property and `recompute_content_hash()` method on SDK `Skill` class
- Content hash written to `.agr.json` at install time (both local and remote)
- Content hash preserved during `agr sync` metadata migrations

## [0.7.8] - 2026-03-02

### Added
- `agr onboard` interactive guided setup command: walks through tool selection, skill discovery, migration, and configuration
- `agr --quiet` / `-q` global flag to suppress non-error output across all commands
- `agr/detect.py` module for signal-based tool detection (checks for `.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, etc.)
- `agr/console.py` shared console factory that respects the quiet flag
- Auto-detect tools when `agr add` creates a new `agr.toml` (uses the same signal-based detection)
- Tests for onboard, quiet mode, and tool detection

### Changed
- `agr init` simplified: removed `--interactive`, `--migrate`, and `--prefer` flags (interactive setup moved to `agr onboard`)
- `agr init` no longer discovers or adds skills to config (that responsibility moved to `agr onboard`)
- `agr init` uses signal-based tool detection instead of checking for tool skills directories
- Replaced module-level `Console()` instances with lazy `get_console()` calls to support the quiet flag
- `agr init` hints at `agr onboard` instead of `agr sync` as the next step

### Removed
- `--interactive` / `-i` flag from `agr init`
- `--migrate` and `--prefer` flags from `agr init`
- Skill discovery, migration, and deduplication logic from `agr/commands/init.py` (moved to onboard)

### Docs
- Updated README, docs/index.md, and docs/reference.md to reflect `agr init` simplification and new `agr onboard` command
- Removed references to deleted `--interactive`, `--migrate`, `--prefer` flags
- Added `agr onboard` to command tables and reference
- Added "Global Options" section to reference documenting `--quiet/-q` and `--version/-v`

## [0.7.7] - 2026-03-02

### Fixed
- `agr config set/add/remove tools --global` no longer calls `find_repo_root()` or syncs/deletes repo-local skills
- `_sync_dependencies_to_tools` return value is now checked; non-zero exits with error
- `agr config edit` handles `$EDITOR` with flags (e.g. `"code --wait"`) via `shlex.split`
- `agr config edit` propagates editor exit code
- `agr config path --global` errors when `~/.agr/agr.toml` doesn't exist instead of printing a nonexistent path
- Hardcoded `~/.agr/agr.toml` in `_load_config` error message replaced with actual path
- `agr config add/remove sources` rejects extra values (only one source name at a time)

### Changed
- Extracted `VALID_CANONICAL_INSTRUCTIONS` constant in `agr/config.py`, shared with `config_cmd.py`
- Extracted `GlobalScope` type alias in `agr/main.py` replacing 8 duplicate `Annotated` definitions
- Added `else: raise AssertionError` guards to key dispatch chains in `run_config_get/set/unset`
- `agr config add tools` skips `config.save()` when no tools were actually added

### Added
- 14 new CLI tests for config edit, default_source, sync_instructions, canonical_instructions, type flags, unconfigured tools, extra values, and deprecation warnings

## [0.7.6] - 2026-03-02

### Added
- Helpful suggestions when a two-part handle (e.g. `agr add owner/repo`) fails: probes the repo and lists available skills with correct three-part handles
- `list_remote_repo_skills` function to scan a remote repo for available skills
- `discover_skills_in_repo_listing` function to extract all skill names from a git file listing
- "Coming from npx skills?" section in README explaining handle format differences

### Changed
- Refactored `find_skill_in_repo_listing` to use shared `_iter_skill_dirs_in_listing` helper
- Cleaned up `agr.toml` dependencies (removed duplicates and non-existent skills)
- Added `.opencode/` to `.gitignore`

## [0.7.5] - 2026-02-07

### Added
- `agr config` command group with `tools` and `default-tool` subcommands
- Global scope flags (`-g`, `--global`) for `agr add`, `agr remove`, `agr sync`, and `agr list`
- Global config helpers for `~/.agr/agr.toml`
- Cross-platform cache lock backends in SDK cache (`msvcrt` on Windows, `fcntl` on POSIX)
- CLI tests for `agr config` commands and global flag flows
- SDK cache tests for Windows and POSIX lock wrappers

### Changed
- `agr tools` now behaves as a deprecated alias of `agr config tools` with a warning
- Fetch/install helpers now support global installs via explicit skills directory overrides
- README and reference docs now document `agr config` and global install/list/sync/remove commands
- Docs tests now validate `agr config` command documentation

### Fixed
- Global local dependencies are stored as absolute paths so `sync -g` and `remove -g` work reliably across directories
- SDK cache no longer hard-depends on Unix-only `fcntl` lock calls

## [0.7.4] - 2026-02-06
### Added
- Antigravity tool support with workspace `.agent/skills/` and global `~/.gemini/antigravity/skills/` paths
- Antigravity CLI tests and documentation updates

## [0.7.3] - 2026-02-04
### Changed
- Owner-only handles now default to the `skills` repo with a warning-backed fallback to `agent-resources`

### Fixed
- `agr sync` now respects per-dependency sources for owner-only handles


## [0.7.2] - 2026-02-02

### Added
- **SDK module** for programmatic access to skills (`from agr import Skill, cache, list_skills, skill_info`)
- `Skill.from_git(handle)` - Load skills from GitHub repositories with automatic caching
- `Skill.from_local(path)` - Load skills from local directories
- `list_skills(repo)` - Discover skills in a GitHub repository
- `skill_info(handle)` - Get metadata about a skill without downloading
- `cache` manager for inspecting and clearing the skill cache
- `SkillInfo` dataclass with name, handle, description, owner, and repo fields
- `CacheError` and `RateLimitError` exception types
- Path traversal protection in cache operations and `Skill.read_file()`
- Atomic cache writes with file locking to prevent race conditions

### Changed
- Remote skill fetching now resolves the default branch before cloning
- agrx temporary installs use unique names and share the remote install helper
- Root `agr` package now re-exports SDK types: `Skill`, `SkillInfo`, `cache`, `list_skills`, `skill_info`

### Fixed
- Lint fixes in changelog workflow scripts

## [0.7.2b3] - 2026-01-31

### Added
- OpenCode tool support with `.opencode/skill/` install path, CLI integration, and docs updates

## [0.7.2b2] - 2026-01-31

### Added
- `agr init` now auto-discovers local skills, detects tool folders, and can migrate tool-folder skills into `./skills/`
- New configuration keys for tool defaults and instruction sync: `default_tool`, `sync_instructions`, `canonical_instructions`
- Instruction file sync during `agr sync` when configured for multiple tools
- New bundled skills: discover-assumptions, discover-opportunities, discover-outcomes, enhance-docs, skriv-som-kasper

### Changed
- `agr sync` reuses a single repo download to install multiple skills from the same source
- `agrx` now uses `default_tool` from `agr.toml` when set
- Handle parsing prefers existing local paths unless explicitly parsing remote handles

### Fixed
- Local installs now backfill missing metadata when the source path already matches the destination

### Removed
- GitHub Actions workflows for docs and publish automation

## [0.7.2b1] - 2026-01-31

### Added
- Multi-source configuration with `default_source` and `[[source]]` entries in `agr.toml`
- `--source` flag on CLI commands to explicitly select a source

### Changed
- Remote skill fetching now uses git clone with sparse checkout for faster, auth-flexible downloads
- Skill metadata now records source to disambiguate duplicate names across sources

### Fixed
- Small fixes across CLI, docs, and tests

## [0.7.1] - 2026-01-29

### Added
- Sync migration for flat tools now records metadata for accurate matching
- Codex CLI coverage in tool and agrx test suites
- ToolConfig fields for tool-specific exec/continue commands, prompt modes, and skill prefixes

### Changed
- Flat tools install skills using the plain skill name by default, falling back to full handle on collisions
- Local skill installs now reject duplicate skill names across tools
- Sync now migrates flat `user--repo--skill` directories to plain names when safe
- Docs now reference the configured tool instead of Claude-only language
- agrx skill invocation now respects tool-specific prompt modes, nested skill paths, and non-interactive exec handling
- Default tools list now includes Codex and refreshes bundled skill dependencies
- `.gitignore` now ignores `.codex/` and `.github/skills/` instead of all of `.github/`

### Removed
- `agent-feedback` skill

## [0.7.1b2] - 2026-01-28

### Added
- `agr tools` command group for managing configured tools (`list`, `add`, `remove`)
- Multi-tool support in `agrx` with `--tool` flag to specify which CLI to use
- CLI configuration fields in `ToolConfig` (`cli_command`, `cli_prompt_flag`, `cli_force_flag`, etc.)

### Fixed
- Config now saved after sync completes in `agr tools add`, preventing data inconsistency if sync fails
- Tool not removed from config if skill deletion fails in `agr tools remove`, preventing orphaned files
- Use `DEFAULT_TOOL_NAMES[0]` constant instead of hardcoded "claude" in agrx fallback
- Add type annotation to `_check_tool_cli()` in agrx
- Remove dead code (unused variable assignment) in agrx

## [0.7.1b1] - 2026-01-27

### Added
- GitHub Copilot support with flat directory structure (`.github/skills/` for project, `~/.copilot/skills/` for global)
- `global_config_dir` field in `ToolConfig` for tools where personal path differs from project path
- Private repository support via GITHUB_TOKEN/GH_TOKEN environment variables
- `AuthenticationError` exception for authentication failures (401/403 responses)
- Comprehensive test coverage for GitHub authentication and error handling
- CLI integration tests for Cursor tool support (`test_cursor.py`)
- CLI integration tests for GitHub Copilot tool support (`test_copilot.py`)
- CLI integration tests for private repo authentication (`test_private_repo.py`)
- Tests for multi-tool scenarios (Claude + Cursor, Claude + Copilot)
- Token security tests ensuring credentials are not leaked in error messages

## [0.7.0] - 2026-01-27

### Added
- `@pytest.mark.requires_cli(name)` marker to skip tests when required CLI tools aren't installed
- **Multi-tool support**: Skills can now be installed to multiple AI coding tools simultaneously
- CLI testing infrastructure with fluent assertion API (`assert_cli(result).succeeded().stdout_contains("...")`)
- Test coverage for `agr add`, `remove`, `init`, `sync`, `list`, `--version`, `--help`
- Test coverage for `agrx` command with network marker for external dependency tests
- Edge case tests: adding already-installed skill, removing non-installed skill, init with existing directory
- Negative assertion helpers: `stdout_not_contains()`, `stderr_not_contains()`
- `@pytest.mark.network` marker for tests requiring network access (skip with `-m "not network"`)
- Cursor tool configuration with nested directory structure (e.g., `.cursor/skills/username/skill/`)
- `tools` configuration in `agr.toml` to specify target tools: `tools = ["claude", "cursor"]`
- `fetch_and_install_to_tools()` function for atomic multi-tool installation with rollback
- Validation that empty tools list raises `ValueError` in `fetch_and_install_to_tools`
- Type hints to `_get_installation_status` in list command

### Changed
- Reorganized `.gitignore` to group tool directories (`.claude/`, `.cursor/`) at top
- `ParsedHandle` now generates tool-appropriate paths (flat for Claude, nested for Cursor)
- Commands (`add`, `remove`, `list`, `sync`) now operate on all configured tools
- Rollback failures in `fetch_and_install_to_tools` now log warnings instead of being silently ignored
- Extracted common installation logic into `_copy_skill_to_destination` helper (DRY refactor)
- Tool names in `agr.toml` are now validated at config load time, catching typos early
- Error messages in `agr remove` now distinguish between "not found" and actual errors
- Release workflow now extracts notes from CHANGELOG.md instead of requiring RELEASE_NOTES.md
- Workflow checkouts the tag directly (fixes race condition with main branch)
- Only release job has contents:write permission (security improvement)
- Added tag format validation in workflow
- Updated /make-release skill to match new automated workflow (6 steps instead of 8)

### Fixed
- Fix import order in `fetcher.py` to resolve E402 linting errors
- Use `SKILL_MARKER` constant instead of hardcoded `"SKILL.md"` string in sync command
- Shell injection risk in workflow by using environment variables instead of direct interpolation
- Hardcoded repository URL in release notes now uses GitHub context variables

## [0.6.4] - 2026-01-27

### Fixed
- Fix CI/CD publish workflow to use virtualenv instead of system Python

## [0.6.3] - 2026-01-27

### Fixed
- Added dev dependencies (ruff, pytest) to pyproject.toml for CI/CD
- Fixed linting and formatting issues for ruff compatibility

## [0.6.2] - 2026-01-27

### Changed
- Use `--` separator instead of `:` for installed skill directory names (Windows compatibility)
- Installed names now use format `username--skill` instead of `username:skill`
- Local skills use `local--skillname` instead of `local:skillname`

### Added
- Development workflow skills: `/research`, `/discover-solution-space`, `/make-plan`, `/code-review`, `/make-commit`, `/make-release`
- Skills implement a structured feature development cycle: research → solution exploration → planning → code review → commit → release
- Automatic migration of legacy colon-based directories during `agr sync`
- Validation to reject handles containing reserved `--` sequence
- Backward compatibility for parsing legacy colon-format installed names
- Comprehensive tests for separator migration and validation
- GitHub Actions workflow for automated PyPI publishing via trusted publishing (OIDC)
