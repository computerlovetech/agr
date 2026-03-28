"""Git operations for downloading and preparing repositories."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Generator
from urllib.parse import quote, urlparse, urlunparse

from agr.exceptions import (
    AgrError,
    AuthenticationError,
    RepoNotFoundError,
)
from agr.source import SourceConfig


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


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command with consistent error handling.

    Wraps subprocess.run with standard options (capture output, text mode,
    no check) and ensures OSError is always converted to AgrError.

    Args:
        cmd: Full command list starting with "git".

    Returns:
        CompletedProcess with captured stdout/stderr.

    Raises:
        AgrError: If git cannot be executed (e.g., not installed).
    """
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
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


def get_github_token() -> str | None:
    """Get GitHub token from environment.

    Checks GITHUB_TOKEN first, then falls back to GH_TOKEN (used by gh CLI).

    Returns:
        Token string if set and non-empty, None otherwise.
    """
    for env_var in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(env_var, "")
        if token.strip():
            return token.strip()
    return None


def get_head_commit(repo_dir: Path) -> str:
    """Get the HEAD commit hash of a repository (truncated to 12 chars).

    If the git command fails (e.g. not a git repo), generates a unique
    fallback hash based on current time and repo path to ensure proper
    cache busting.
    """
    result = _run_git(_git_cmd(repo_dir, "rev-parse", "HEAD"))
    if result.returncode != 0:
        fallback_data = f"{time.time_ns()}:{repo_dir}"
        return hashlib.sha256(fallback_data.encode()).hexdigest()[:12]
    return result.stdout.strip()[:12]


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


def _apply_github_token(repo_url: str) -> str:
    """Inject GitHub token into HTTPS URL if available."""
    token = get_github_token()
    if not token:
        return repo_url
    parsed = urlparse(repo_url)
    if parsed.scheme != "https":
        return repo_url
    if not parsed.netloc.endswith("github.com"):
        return repo_url
    if "@" in parsed.netloc:
        return repo_url
    encoded = quote(token, safe="")
    netloc = f"{encoded}:x-oauth-basic@{parsed.netloc}"
    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


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
    if "authentication failed" in lowered or "permission denied" in lowered:
        if token_missing:
            raise AuthenticationError(
                f"Authentication failed for source '{source.name}'. "
                "Repository not found or requires authentication."
            ) from None
        raise AuthenticationError(
            f"Authentication failed for source '{source.name}'."
        ) from None

    # 2. Explicit "not found" responses from the server
    if (
        "repository not found" in lowered
        or ("not found" in lowered and "repository" in lowered)
        or "does not exist" in lowered
    ):
        raise RepoNotFoundError(
            f"Repository '{owner}/{repo_name}' not found in source '{source.name}'."
        ) from None

    # 3. DNS / network failures
    if "could not resolve host" in lowered:
        raise AgrError(
            f"Network error: could not resolve host for source '{source.name}'."
        ) from None

    # 4. Heuristic: when no token is set, ambiguous errors likely mean the
    # repo is private or doesn't exist. We report "not found" to guide the
    # user toward setting GITHUB_TOKEN. This includes empty stderr (git
    # sometimes exits non-zero with no output when auth is needed).
    if token_missing and (
        not lowered
        or "could not read username" in lowered  # no credential helper
        or "terminal prompts disabled" in lowered  # GIT_TERMINAL_PROMPT=0
        or "authentication required" in lowered
        or "authorization failed" in lowered
        or "access denied" in lowered
    ):
        raise RepoNotFoundError(
            f"Repository '{owner}/{repo_name}' not found in source '{source.name}'."
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
    repo_url = _apply_github_token(repo_url)
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
    cmd = _git_cmd(repo_dir, "sparse-checkout", "set")
    cmd.extend([rel_path.as_posix() for rel_path in rel_paths])
    _run_git_checked(cmd, "Failed to set sparse checkout path.")
    checkout_full(repo_dir)
