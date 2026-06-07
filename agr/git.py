"""Git operations for downloading and preparing repositories."""

import base64
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Generator
from agr.auth import StoredGitHubCredential, read_stored_github_credential
from agr.exceptions import (
    AgrError,
    AuthenticationError,
    RepoNotFoundError,
)
from agr.source import SourceConfig

SHORT_HASH_LENGTH = 12
"""Number of hex characters used for abbreviated commit hashes."""

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
"""Regex matching a full 40-character lowercase hex git commit SHA."""


def _git_cmd(repo_dir: Path, *args: str) -> list[str]:
    """Build a git command targeting a specific repository.

    Constructs ``["git", "-C", <repo_dir>, *args]`` to run git
    in the given directory without changing the working directory.

    Args:
        repo_dir: Path to the repository.
        *args: Git subcommand and its arguments.

    Returns:
        Command list ready for ``_run_git`` or ``_run_git_checked``.
    """
    return ["git", "-C", str(repo_dir), *args]


def _build_github_auth_env() -> dict[str, str]:
    """Build env vars to authenticate git HTTP requests to GitHub.

    Uses ``GIT_CONFIG_COUNT``/``GIT_CONFIG_KEY_N``/``GIT_CONFIG_VALUE_N``
    (git 2.31+) to inject an ``Authorization`` header scoped to
    ``https://github.com/``.  This avoids embedding the token in the
    git URL, which would expose it in process listings (``ps aux``,
    ``/proc/PID/cmdline``).

    Returns:
        Dict of env var overrides.  Empty when no token is available.
    """
    credential = get_github_credential()
    if not credential:
        return {}

    try:
        existing_count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        existing_count = 0
    basic_token = _build_basic_auth_token(credential)
    return {
        "GIT_CONFIG_COUNT": str(existing_count + 1),
        f"GIT_CONFIG_KEY_{existing_count}": ("http.https://github.com/.extraheader"),
        f"GIT_CONFIG_VALUE_{existing_count}": (f"AUTHORIZATION: basic {basic_token}"),
    }


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command with consistent error handling.

    Wraps subprocess.run with standard options (capture output, text mode,
    no check) and ensures OSError is always converted to AgrError.

    GitHub authentication is handled automatically via env-based git
    config (``http.extraheader``) so tokens never appear in process
    command-line arguments.

    Args:
        cmd: Full command list starting with "git".

    Returns:
        CompletedProcess with captured stdout/stderr.

    Raises:
        AgrError: If git cannot be executed (e.g., not installed).
    """
    auth_env = _build_github_auth_env()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **auth_env}
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as e:
        raise AgrError(f"Failed to run git: {type(e).__name__}") from None


def _run_git_checked(
    cmd: list[str], error_message: str
) -> subprocess.CompletedProcess[str]:
    """Run a git command and raise AgrError on non-zero exit.

    Convenience wrapper around ``_run_git`` for commands where any
    non-zero return code is a fatal error with a fixed message.

    Args:
        cmd: Full command list starting with "git".
        error_message: Message for the AgrError raised on failure.

    Returns:
        CompletedProcess with captured stdout/stderr.

    Raises:
        AgrError: If the command exits with a non-zero return code,
            or if git cannot be executed.
    """
    result = _run_git(cmd)
    if result.returncode != 0:
        raise AgrError(error_message)
    return result


def get_github_credential() -> StoredGitHubCredential | None:
    for env_var in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(env_var, "")
        if token.strip():
            return StoredGitHubCredential(
                method="env",
                token=token.strip(),
                username="x-access-token",
            )
    return read_stored_github_credential()


def get_github_token() -> str | None:
    credential = get_github_credential()
    return credential.token if credential else None


def _build_basic_auth_token(credential: StoredGitHubCredential) -> str:
    username = (
        credential.username
        if credential.method == "username_password"
        else "x-access-token"
    )
    if credential.method == "username_password" and not username:
        return ""
    return base64.b64encode(f"{username}:{credential.token}".encode()).decode()


def short_commit(commit: str) -> str:
    """Abbreviate a full commit hash to ``SHORT_HASH_LENGTH`` characters."""
    return commit[:SHORT_HASH_LENGTH]


def get_head_commit(repo_dir: Path) -> str:
    """Get the HEAD commit hash of a repository (truncated).

    If the git command fails (e.g. not a git repo), generates a unique
    fallback hash based on current time and repo path to ensure proper
    cache busting.
    """
    result = _run_git(_git_cmd(repo_dir, "rev-parse", "HEAD"))
    if result.returncode != 0:
        fallback_data = f"{time.time_ns()}:{repo_dir}"
        return short_commit(hashlib.sha256(fallback_data.encode()).hexdigest())
    return short_commit(result.stdout.strip())


def get_head_commit_full(repo_dir: Path) -> str:
    """Get the full HEAD commit hash of a repository (40 hex chars).

    Unlike ``get_head_commit``, this raises on failure instead of
    generating a fallback — the lockfile needs real commit SHAs.
    """
    result = _run_git(_git_cmd(repo_dir, "rev-parse", "HEAD"))
    if result.returncode != 0:
        raise AgrError("Failed to determine HEAD commit for lockfile.")
    return result.stdout.strip()


def safe_get_head_commit(repo_dir: Path) -> str | None:
    """Get the full HEAD commit hash, returning None on failure.

    Convenience wrapper around :func:`get_head_commit_full` for callers
    that record an optional commit (e.g. lockfile metadata) and can
    tolerate missing values.
    """
    try:
        return get_head_commit_full(repo_dir)
    except AgrError:
        return None


def validate_commit_sha(commit: str) -> None:
    """Validate that a string is a full 40-character hex git commit SHA.

    Prevents non-SHA refs (branch names, tags, etc.) from being used
    where a pinned commit is expected.  This is security-critical for
    ``--frozen`` sync, which trusts the lockfile to specify exact
    immutable commits — accepting arbitrary refs would allow a
    tampered lockfile to silently install different code.

    Raises:
        AgrError: If the string is not a valid full SHA.
    """
    if not _FULL_SHA_RE.match(commit):
        raise AgrError(
            f"Invalid commit SHA '{short_commit(commit)}': "
            "expected a 40-character hex hash. "
            "The lockfile may be corrupted or tampered with."
        )


def fetch_and_checkout_commit(repo_dir: Path, commit: str) -> None:
    """Fetch a specific commit and check it out.

    Used by ``--frozen`` sync to pin to lockfile commits.
    Works with depth-1 clones on GitHub by fetching the exact SHA.

    Always ensures the working tree is populated, even when HEAD
    already matches *commit* — partial clones use ``--no-checkout``
    so the working tree may be empty after the initial clone.

    Raises:
        AgrError: If *commit* is not a valid full SHA, or if the
            fetch/checkout fails.
    """
    validate_commit_sha(commit)
    current = get_head_commit_full(repo_dir)
    if current == commit:
        checkout_full(repo_dir)
        return

    result = _run_git(_git_cmd(repo_dir, "fetch", "--depth=1", "origin", commit))
    if result.returncode != 0:
        raise AgrError(
            f"Failed to fetch commit {short_commit(commit)}. The commit may no longer exist."
        )

    _run_git_checked(
        _git_cmd(repo_dir, "checkout", commit),
        f"Failed to checkout commit {short_commit(commit)}.",
    )


def _is_github_source(source: SourceConfig) -> bool:
    """Return True if the source URL points to GitHub."""
    return "github.com" in source.url.lower()


def _get_default_branch(repo_url: str) -> str | None:
    """Return the default branch name for a remote repo, if detectable."""
    result = _run_git(["git", "ls-remote", "--symref", repo_url, "HEAD"])

    if result.returncode != 0:
        return None

    # Expected: "ref: refs/heads/main\tHEAD"
    for line in result.stdout.splitlines():
        if not line.startswith("ref:"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith("refs/heads/"):
            return ref.replace("refs/heads/", "", 1)
    return None


def _clone_repo(
    repo_url: str, repo_dir: Path, partial: bool, branch: str | None
) -> subprocess.CompletedProcess[str]:
    """Clone a repository using git, optionally with partial clone flags."""
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
    ]
    if branch:
        cmd.extend(["--branch", branch])
    if partial:
        cmd.extend(["--filter=blob:none", "--no-checkout"])
    cmd.extend([repo_url, str(repo_dir)])
    return _run_git(cmd)


def _partial_clone_unsupported(stderr: str | None) -> bool:
    """Detect errors indicating partial clone is unsupported."""
    if not stderr:
        return False
    # Different git versions and servers report partial clone failures with
    # different messages. We check all known variants so the caller can
    # fall back to a full clone.
    lowered = stderr.lower()
    return (
        ("unknown option" in lowered and "--filter" in lowered)  # old git client
        or "filtering is not supported" in lowered  # server rejects filter
        or "does not support filtering" in lowered  # alternate server phrasing
        or "filtering not recognized" in lowered  # rare git builds
    )


def _reset_repo_dir(repo_dir: Path) -> None:
    """Remove a partially created repo directory."""
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)


def _is_explicit_auth_failure(lowered: str) -> bool:
    """Detect explicit authentication failures from git credential helpers."""
    return "authentication failed" in lowered or "permission denied" in lowered


def _is_repo_not_found(lowered: str) -> bool:
    """Detect explicit 'repository not found' responses from the server."""
    return (
        "repository not found" in lowered
        or ("not found" in lowered and "repository" in lowered)
        or "does not exist" in lowered
    )


def _is_network_error(lowered: str) -> bool:
    """Detect DNS / network failures."""
    return "could not resolve host" in lowered


def _is_ambiguous_auth_hint(lowered: str) -> bool:
    """Detect ambiguous errors that likely indicate missing authentication.

    When no GitHub token is set, these errors suggest the repo is private
    or doesn't exist.  Includes the empty-message case — git sometimes
    exits non-zero with no output when auth is needed.
    """
    return (
        not lowered
        or "could not read username" in lowered  # no credential helper
        or "terminal prompts disabled" in lowered  # GIT_TERMINAL_PROMPT=0
        or "authentication required" in lowered
        or "authorization failed" in lowered
        or "access denied" in lowered
    )


def _raise_clone_error(
    stderr: str | None,
    owner: str,
    repo_name: str,
    source: SourceConfig,
    stdout: str | None = None,
) -> None:
    """Raise a friendly error based on git clone output.

    Classifies git stderr/stdout into specific exception types so callers
    get actionable errors. The classification order matters: explicit auth
    failures first, then repo-not-found, then network errors, then a
    heuristic catch-all for missing tokens.
    """
    message = "\n".join(
        part for part in ((stderr or "").strip(), (stdout or "").strip()) if part
    ).strip()
    lowered = message.lower()
    # When no GitHub token is set, many "not found" errors are actually
    # auth failures in disguise — GitHub returns 404 for private repos
    # that the user can't access, rather than 403.
    token_missing = _is_github_source(source) and not get_github_token()

    # 1. Explicit authentication failures (git credential helper responded)
    if _is_explicit_auth_failure(lowered):
        if token_missing:
            raise AuthenticationError(
                f"Authentication failed for source '{source.name}'. "
                "Repository not found or requires authentication. "
                "Run 'agr auth login' or set GITHUB_TOKEN/GH_TOKEN."
            ) from None
        raise AuthenticationError(
            f"Authentication failed for source '{source.name}'. "
            "Run 'agr auth login' or set GITHUB_TOKEN/GH_TOKEN."
        ) from None

    # 2. Explicit "not found" responses from the server
    if _is_repo_not_found(lowered):
        raise RepoNotFoundError(
            f"Repository '{owner}/{repo_name}' not found in source '{source.name}'. "
            "If this is a private repository, run 'agr auth login' or set GITHUB_TOKEN/GH_TOKEN."
        ) from None

    # 3. DNS / network failures
    if _is_network_error(lowered):
        raise AgrError(
            f"Network error: could not resolve host for source '{source.name}'."
        ) from None

    # 4. Heuristic: when no token is set, ambiguous errors likely mean the
    # repo is private or doesn't exist. We report "not found" to guide the
    # user toward setting GITHUB_TOKEN.
    if token_missing and _is_ambiguous_auth_hint(lowered):
        raise RepoNotFoundError(
            f"Repository '{owner}/{repo_name}' not found in source '{source.name}'. "
            "Run 'agr auth login' or set GITHUB_TOKEN/GH_TOKEN for private repositories."
        ) from None

    # 5. Catch-all for unrecognized errors
    raise AgrError(f"Failed to clone repository from source '{source.name}'.") from None


@contextmanager
def downloaded_repo(
    source: SourceConfig, owner: str, repo_name: str
) -> Generator[Path, None, None]:
    """Download a git repo and yield the extracted directory.

    Args:
        source: Source configuration
        owner: Repo owner/username
        repo_name: Repository name

    Yields:
        Path to cloned repository directory

    Raises:
        RepoNotFoundError: If the repository doesn't exist
        AuthenticationError: If authentication fails (private repo without valid token)
        AgrError: If download fails
    """
    if shutil.which("git") is None:
        raise AgrError("git CLI not found. Install git to fetch remote skills.")

    repo_url = source.build_repo_url(owner, repo_name)
    # Token is passed via env-based git config in _run_git, not in the URL.
    default_branch = _get_default_branch(repo_url)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        repo_dir = tmp_path / "repo"

        result = _clone_repo(repo_url, repo_dir, partial=True, branch=default_branch)
        if result.returncode != 0 and _partial_clone_unsupported(result.stderr):
            _reset_repo_dir(repo_dir)
            result = _clone_repo(
                repo_url, repo_dir, partial=False, branch=default_branch
            )

        if result.returncode != 0:
            _raise_clone_error(
                result.stderr,
                owner,
                repo_name,
                source,
                stdout=result.stdout,
            )

        yield repo_dir


def git_list_files(repo_dir: Path) -> list[str]:
    """List files in the repo without checking out blobs."""
    result = _run_git_checked(
        _git_cmd(repo_dir, "ls-tree", "-r", "--name-only", "HEAD"),
        "Failed to list repository files.",
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def checkout_full(repo_dir: Path) -> None:
    """Checkout the working tree from HEAD.

    Works regardless of the default branch name (main, master, etc.)
    because it checks out whatever HEAD points to rather than
    hardcoding a branch name.
    """
    _run_git_checked(
        _git_cmd(repo_dir, "checkout", "-f", "HEAD"),
        "Failed to checkout repository.",
    )


def checkout_sparse_paths(repo_dir: Path, rel_paths: list[Path]) -> None:
    """Checkout only the given paths using sparse checkout."""
    if not rel_paths:
        raise AgrError("No paths provided for sparse checkout.")
    _run_git_checked(
        _git_cmd(repo_dir, "sparse-checkout", "init", "--cone"),
        "Failed to initialize sparse checkout.",
    )
    cmd = _git_cmd(repo_dir, "sparse-checkout", "set", "--")
    cmd.extend([rel_path.as_posix() for rel_path in rel_paths])
    _run_git_checked(cmd, "Failed to set sparse checkout path.")
    checkout_full(repo_dir)
