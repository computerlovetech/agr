import json
import stat
from pathlib import Path

import pytest

from agr.auth import (
    AuthStatus,
    DeviceAuthorization,
    FileTokenStore,
    GitHubAuthStatusChecker,
    OAuthGitHubLoginStrategy,
    StoredGitHubCredential,
    UsernamePasswordGitHubLoginStrategy,
    login,
    logout,
    status,
)
from agr.exceptions import AgrError


class FakeOAuthClient:
    def __init__(self) -> None:
        self.authorization = DeviceAuthorization(
            "device",
            "USER-CODE",
            "https://github.com/login/device",
            900,
            1,
        )
        self.token = "stored-token"

    def request_device_authorization(self) -> DeviceAuthorization:
        return self.authorization

    def poll_for_token(self, authorization: DeviceAuthorization) -> str:
        assert authorization == self.authorization
        return self.token


class MemoryTokenStore:
    def __init__(self, credential: StoredGitHubCredential | None = None) -> None:
        self.credential = credential
        self.deleted = False

    def read_credential(self) -> StoredGitHubCredential | None:
        return self.credential

    def write_credential(self, credential: StoredGitHubCredential) -> None:
        self.credential = credential

    def read_token(self) -> str | None:
        return self.credential.token if self.credential else None

    def write_token(self, token: str) -> None:
        self.credential = StoredGitHubCredential(method="oauth", token=token)

    def delete_token(self) -> bool:
        had_token = self.credential is not None
        self.credential = None
        self.deleted = True
        return had_token


def test_file_token_store_writes_reads_and_sets_permissions(tmp_path: Path) -> None:
    auth_file = tmp_path / ".agr" / "auth.json"
    store = FileTokenStore(auth_file)
    credential = StoredGitHubCredential(
        method="username_password",
        token=" token-value ",
        username=" octocat ",
    )

    store.write_credential(credential)

    assert store.read_credential() == StoredGitHubCredential(
        method="username_password",
        token="token-value",
        username="octocat",
    )
    assert json.loads(auth_file.read_text()) == {
        "github_token": "token-value",
        "method": "username_password",
        "username": "octocat",
    }
    assert stat.S_IMODE(auth_file.stat().st_mode) == 0o600


def test_file_token_store_reads_backcompat_token_format(tmp_path: Path) -> None:
    auth_file = tmp_path / ".agr" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text(json.dumps({"github_token": " stored-token "}))
    store = FileTokenStore(auth_file)

    assert store.read_credential() == StoredGitHubCredential(
        method="oauth",
        token="stored-token",
    )
    assert store.read_token() == "stored-token"


def test_file_token_store_write_token_uses_oauth_method(tmp_path: Path) -> None:
    auth_file = tmp_path / ".agr" / "auth.json"
    store = FileTokenStore(auth_file)

    store.write_token(" token-value ")

    assert store.read_credential() == StoredGitHubCredential(
        method="oauth",
        token="token-value",
    )


def test_file_token_store_delete_removes_file(tmp_path: Path) -> None:
    auth_file = tmp_path / ".agr" / "auth.json"
    store = FileTokenStore(auth_file)
    store.write_token("token-value")

    assert store.delete_token() is True
    assert store.read_token() is None
    assert store.delete_token() is False


def test_file_token_store_ignores_missing_invalid_and_empty_files(
    tmp_path: Path,
) -> None:
    auth_file = tmp_path / ".agr" / "auth.json"
    store = FileTokenStore(auth_file)

    assert store.read_token() is None
    auth_file.parent.mkdir()
    auth_file.write_text("not-json")
    assert store.read_token() is None
    auth_file.write_text(json.dumps({"github_token": "   "}))
    assert store.read_token() is None


def test_file_token_store_rejects_empty_token(tmp_path: Path) -> None:
    store = FileTokenStore(tmp_path / ".agr" / "auth.json")

    with pytest.raises(AgrError, match="empty"):
        store.write_token("   ")


def test_file_token_store_rejects_username_password_without_username(
    tmp_path: Path,
) -> None:
    store = FileTokenStore(tmp_path / ".agr" / "auth.json")

    with pytest.raises(AgrError, match="username"):
        store.write_credential(
            StoredGitHubCredential(method="username_password", token="token")
        )


def test_auth_status_checker_prefers_environment_tokens() -> None:
    store = MemoryTokenStore(
        StoredGitHubCredential(method="oauth", token="stored-token")
    )
    checker = GitHubAuthStatusChecker(
        store, {"GITHUB_TOKEN": " github-token ", "GH_TOKEN": "gh-token"}
    )

    result = checker.get_status()

    assert result == AuthStatus(authenticated=True, source="GITHUB_TOKEN", method="env")


def test_status_prefers_environment_tokens() -> None:
    store = MemoryTokenStore(
        StoredGitHubCredential(method="oauth", token="stored-token")
    )

    result = status(store, {"GITHUB_TOKEN": " github-token ", "GH_TOKEN": "gh-token"})

    assert result == AuthStatus(authenticated=True, source="GITHUB_TOKEN", method="env")


def test_status_uses_gh_token_before_stored_token() -> None:
    store = MemoryTokenStore(
        StoredGitHubCredential(method="oauth", token="stored-token")
    )

    result = status(store, {"GH_TOKEN": "gh-token"})

    assert result == AuthStatus(authenticated=True, source="GH_TOKEN", method="env")


def test_status_uses_stored_token() -> None:
    store = MemoryTokenStore(
        StoredGitHubCredential(method="username_password", token="stored-token")
    )

    result = status(store, {})

    assert result == AuthStatus(
        authenticated=True,
        source="stored",
        method="username_password",
    )


def test_status_reports_not_authenticated() -> None:
    assert status(MemoryTokenStore(), {}) == AuthStatus(
        authenticated=False,
        source=None,
        method=None,
    )


def test_username_password_strategy_uses_values() -> None:
    strategy = UsernamePasswordGitHubLoginStrategy(
        username=" octocat ",
        password=" secret-token ",
    )

    assert strategy.login() == StoredGitHubCredential(
        method="username_password",
        token="secret-token",
        username="octocat",
    )


def test_username_password_strategy_uses_prompts() -> None:
    strategy = UsernamePasswordGitHubLoginStrategy(
        username_prompt=lambda: "octocat",
        password_prompt=lambda: "secret-token",
    )

    assert strategy.login() == StoredGitHubCredential(
        method="username_password",
        token="secret-token",
        username="octocat",
    )


def test_username_password_strategy_rejects_empty_values() -> None:
    strategy = UsernamePasswordGitHubLoginStrategy(username="octocat", password=" ")

    with pytest.raises(AgrError, match="password"):
        strategy.login()


def test_oauth_strategy_calls_prompt_and_polls() -> None:
    oauth = FakeOAuthClient()
    prompts: list[DeviceAuthorization] = []
    strategy = OAuthGitHubLoginStrategy(oauth, prompts.append)

    credential = strategy.login()

    assert credential == StoredGitHubCredential(method="oauth", token="stored-token")
    assert prompts == [oauth.authorization]


def test_login_calls_strategy_and_saves_credential() -> None:
    store = MemoryTokenStore()
    strategy = UsernamePasswordGitHubLoginStrategy(
        username="octocat",
        password="secret-token",
    )

    credential = login(strategy, store)

    assert credential == StoredGitHubCredential(
        method="username_password",
        token="secret-token",
        username="octocat",
    )
    assert store.read_credential() == credential


def test_logout_deletes_token() -> None:
    store = MemoryTokenStore(
        StoredGitHubCredential(method="oauth", token="stored-token")
    )

    assert logout(store) is True
    assert store.read_token() is None
