import json
from pathlib import Path

from tests.cli.assertions import assert_cli
from tests.cli.runner import run_cli


def test_auth_login_default_stores_username_password_credential(tmp_path: Path) -> None:
    result = run_cli(
        ["agr", "auth", "login"],
        env={"HOME": str(tmp_path)},
        input="octocat\nsecret-token\n",
    )

    auth_file = tmp_path / ".agr" / "auth.json"
    assert_cli(result).succeeded().stdout_contains("Authenticated with GitHub")
    assert json.loads(auth_file.read_text()) == {
        "github_token": "secret-token",
        "method": "username_password",
        "username": "octocat",
    }
    assert "secret-token" not in result.stdout
    assert "secret-token" not in result.stderr


def test_auth_login_oauth_uses_device_flow_flag(tmp_path: Path) -> None:
    result = run_cli(
        ["agr", "auth", "login", "--oauth"],
        env={"HOME": str(tmp_path), "AGR_GITHUB_OAUTH_CLIENT_ID": ""},
    )

    assert_cli(result).failed().stdout_contains("GitHub device authorization failed")
    assert "GitHub username" not in result.stdout


def test_auth_login_skips_prompt_when_stored_oauth_token_exists(tmp_path: Path) -> None:
    auth_dir = tmp_path / ".agr"
    auth_dir.mkdir()
    (auth_dir / "auth.json").write_text(
        json.dumps({"github_token": "stored-token", "method": "oauth"})
    )

    result = run_cli(
        ["agr", "auth", "login"],
        env={"HOME": str(tmp_path), "GITHUB_TOKEN": "", "GH_TOKEN": ""},
    )

    assert_cli(result).succeeded().stdout_contains("Already logged in")
    assert "GitHub username" not in result.stdout


def test_auth_login_skips_prompt_when_environment_token_exists(tmp_path: Path) -> None:
    result = run_cli(
        ["agr", "auth", "login"],
        env={"HOME": str(tmp_path), "GITHUB_TOKEN": "github-token"},
    )

    assert_cli(result).succeeded().stdout_contains("Already logged in")
    assert "GitHub username" not in result.stdout


def test_auth_status_reports_environment_token(tmp_path: Path) -> None:
    result = run_cli(
        ["agr", "auth", "status"],
        env={"HOME": str(tmp_path), "GITHUB_TOKEN": "github-token"},
    )

    assert_cli(result).succeeded().stdout_contains("GITHUB_TOKEN environment token")
    assert "github-token" not in result.stdout


def test_auth_status_reports_stored_token(tmp_path: Path) -> None:
    auth_dir = tmp_path / ".agr"
    auth_dir.mkdir()
    (auth_dir / "auth.json").write_text(json.dumps({"github_token": "stored-token"}))

    result = run_cli(
        ["agr", "auth", "status"],
        env={"HOME": str(tmp_path), "GITHUB_TOKEN": "", "GH_TOKEN": ""},
    )

    assert_cli(result).succeeded().stdout_contains("stored agr GitHub token")
    assert "stored-token" not in result.stdout


def test_auth_status_reports_not_authenticated(tmp_path: Path) -> None:
    result = run_cli(
        ["agr", "auth", "status"],
        env={"HOME": str(tmp_path), "GITHUB_TOKEN": "", "GH_TOKEN": ""},
    )

    assert result.returncode == 1
    assert "Not authenticated" in result.stdout
    assert "agr auth login" in result.stdout


def test_auth_logout_removes_stored_token(tmp_path: Path) -> None:
    auth_dir = tmp_path / ".agr"
    auth_dir.mkdir()
    auth_file = auth_dir / "auth.json"
    auth_file.write_text(json.dumps({"github_token": "stored-token"}))

    result = run_cli(["agr", "auth", "logout"], env={"HOME": str(tmp_path)})

    assert_cli(result).succeeded().stdout_contains("Removed stored GitHub token")
    assert not auth_file.exists()


def test_auth_logout_when_no_token_is_successful(tmp_path: Path) -> None:
    result = run_cli(["agr", "auth", "logout"], env={"HOME": str(tmp_path)})

    assert_cli(result).succeeded().stdout_contains("No stored GitHub token found")
