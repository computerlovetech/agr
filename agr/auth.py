import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from agr.exceptions import AgrError

AUTH_DIR_NAME = ".agr"
AUTH_FILE_NAME = "auth.json"
AUTH_FILE_MODE = 0o600


@dataclass(frozen=True)
class StoredGitHubCredential:
    method: str
    token: str
    username: str | None = None


@dataclass(frozen=True)
class StoredToken:
    token: str


@dataclass(frozen=True)
class AuthStatus:
    authenticated: bool
    source: str | None
    method: str | None = None


@dataclass(frozen=True)
class DeviceAuthorization:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class CredentialStore(Protocol):
    def read_credential(self) -> StoredGitHubCredential | None: ...

    def write_credential(self, credential: StoredGitHubCredential) -> None: ...

    def delete_token(self) -> bool: ...


class TokenStore(CredentialStore, Protocol):
    def read_token(self) -> str | None: ...

    def write_token(self, token: str) -> None: ...


class GitHubLoginStrategy(Protocol):
    def login(self) -> StoredGitHubCredential: ...


class DeviceOAuthClient(Protocol):
    def request_device_authorization(self) -> DeviceAuthorization: ...

    def poll_for_token(self, authorization: DeviceAuthorization) -> str: ...


class AuthStatusChecker(Protocol):
    def get_status(self) -> AuthStatus: ...


DevicePromptHandler = Callable[[DeviceAuthorization], None]
StringPrompt = Callable[[], str]


class FileTokenStore:
    def __init__(self, auth_file: Path | None = None) -> None:
        self.auth_file = auth_file or default_auth_file()

    def read_credential(self) -> StoredGitHubCredential | None:
        if not self.auth_file.exists():
            return None
        try:
            data = json.loads(self.auth_file.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        token = data.get("github_token")
        if not isinstance(token, str) or not token.strip():
            return None
        method = data.get("method")
        username = data.get("username")
        normalized_method = method if isinstance(method, str) and method.strip() else "oauth"
        normalized_username = username.strip() if isinstance(username, str) and username.strip() else None
        return StoredGitHubCredential(
            method=normalized_method.strip(),
            token=token.strip(),
            username=normalized_username,
        )

    def write_credential(self, credential: StoredGitHubCredential) -> None:
        token = credential.token.strip()
        method = credential.method.strip()
        username = credential.username.strip() if credential.username else None
        if not token:
            raise AgrError("Cannot store an empty GitHub token.")
        if not method:
            raise AgrError("Cannot store a GitHub credential without a method.")
        if method == "username_password" and not username:
            raise AgrError("Cannot store a username/password credential without a username.")
        data: dict[str, str] = {"github_token": token, "method": method}
        if username:
            data["username"] = username
        self.auth_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            self.auth_file,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            AUTH_FILE_MODE,
        )
        try:
            with os.fdopen(fd, "w") as file:
                json.dump(data, file)
        finally:
            os.chmod(self.auth_file, AUTH_FILE_MODE)

    def read_token(self) -> str | None:
        credential = self.read_credential()
        return credential.token if credential else None

    def write_token(self, token: str) -> None:
        self.write_credential(StoredGitHubCredential(method="oauth", token=token))

    def delete_token(self) -> bool:
        try:
            self.auth_file.unlink()
        except FileNotFoundError:
            return False
        return True


class GitHubAuthStatusChecker:
    def __init__(
        self,
        store: CredentialStore | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.store = store or FileTokenStore()
        self.env = env

    def get_status(self) -> AuthStatus:
        environ = self.env if self.env is not None else os.environ
        for env_var in ("GITHUB_TOKEN", "GH_TOKEN"):
            token = environ.get(env_var, "")
            if token.strip():
                return AuthStatus(authenticated=True, source=env_var, method="env")
        credential = self.store.read_credential()
        if credential:
            return AuthStatus(authenticated=True, source="stored", method=credential.method)
        return AuthStatus(authenticated=False, source=None, method=None)


class UsernamePasswordGitHubLoginStrategy:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        username_prompt: StringPrompt | None = None,
        password_prompt: StringPrompt | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.username_prompt = username_prompt
        self.password_prompt = password_prompt

    def login(self) -> StoredGitHubCredential:
        username = self.username if self.username is not None else self._prompt_username()
        password = self.password if self.password is not None else self._prompt_password()
        normalized_username = username.strip()
        normalized_password = password.strip()
        if not normalized_username:
            raise AgrError("GitHub username cannot be empty.")
        if not normalized_password:
            raise AgrError("GitHub password or token cannot be empty.")
        return StoredGitHubCredential(
            method="username_password",
            token=normalized_password,
            username=normalized_username,
        )

    def _prompt_username(self) -> str:
        if self.username_prompt is None:
            raise AgrError("GitHub username prompt is not configured.")
        return self.username_prompt()

    def _prompt_password(self) -> str:
        if self.password_prompt is None:
            raise AgrError("GitHub password prompt is not configured.")
        return self.password_prompt()


class OAuthGitHubLoginStrategy:
    def __init__(
        self,
        oauth_client: DeviceOAuthClient,
        prompt_handler: DevicePromptHandler | None = None,
    ) -> None:
        self.oauth_client = oauth_client
        self.prompt_handler = prompt_handler

    def login(self) -> StoredGitHubCredential:
        authorization = self.oauth_client.request_device_authorization()
        if self.prompt_handler:
            self.prompt_handler(authorization)
        token = self.oauth_client.poll_for_token(authorization)
        return StoredGitHubCredential(method="oauth", token=token)


def default_auth_file() -> Path:
    return Path.home() / AUTH_DIR_NAME / AUTH_FILE_NAME


def read_stored_github_credential(
    store: CredentialStore | None = None,
) -> StoredGitHubCredential | None:
    return (store or FileTokenStore()).read_credential()


def read_stored_github_token(store: TokenStore | None = None) -> str | None:
    return (store or FileTokenStore()).read_token()


def login(
    strategy: GitHubLoginStrategy,
    store: CredentialStore | None = None,
) -> StoredGitHubCredential:
    token_store = store or FileTokenStore()
    credential = strategy.login()
    token_store.write_credential(credential)
    return credential


def status(store: CredentialStore | None = None, env: dict[str, str] | None = None) -> AuthStatus:
    return GitHubAuthStatusChecker(store, env).get_status()


def logout(store: CredentialStore | None = None) -> bool:
    return (store or FileTokenStore()).delete_token()
