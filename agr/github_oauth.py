import os
import time
from typing import Callable

import httpx

from agr.auth import DeviceAuthorization
from agr.exceptions import AuthenticationError

GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
AGR_GITHUB_OAUTH_CLIENT_ID = "Ov23li9UKn7X2CZq7VIi"
UNCONFIGURED_GITHUB_OAUTH_CLIENT_ID = "replace-with-agr-github-oauth-client-id"
GITHUB_OAUTH_SCOPE = "repo"
MISSING_CLIENT_ID_MESSAGE = (
    "GitHub OAuth login is not configured for this build of agr. "
    "Set AGR_GITHUB_OAUTH_CLIENT_ID to a GitHub OAuth app client ID with device flow enabled, "
    "or set GITHUB_TOKEN/GH_TOKEN."
)


class GitHubOAuthDeviceFlow:
    def __init__(
        self,
        client_id: str = AGR_GITHUB_OAUTH_CLIENT_ID,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client_id = os.environ.get("AGR_GITHUB_OAUTH_CLIENT_ID", client_id)
        self.client = client or httpx.Client(timeout=30)
        self.sleep = sleep

    def request_device_authorization(self) -> DeviceAuthorization:
        if self.client_id == UNCONFIGURED_GITHUB_OAUTH_CLIENT_ID:
            raise AuthenticationError(MISSING_CLIENT_ID_MESSAGE)
        response = self.client.post(
            GITHUB_DEVICE_CODE_URL,
            data={"client_id": self.client_id, "scope": GITHUB_OAUTH_SCOPE},
            headers={"Accept": "application/json"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AuthenticationError(
                f"GitHub device authorization failed: HTTP {exc.response.status_code}."
            ) from None
        data = response.json()
        return DeviceAuthorization(
            device_code=str(data["device_code"]),
            user_code=str(data["user_code"]),
            verification_uri=str(data["verification_uri"]),
            expires_in=int(data["expires_in"]),
            interval=int(data.get("interval", 5)),
        )

    def poll_for_token(self, authorization: DeviceAuthorization) -> str:
        interval = authorization.interval
        deadline = time.monotonic() + authorization.expires_in
        while time.monotonic() < deadline:
            self.sleep(interval)
            response = self.client.post(
                GITHUB_ACCESS_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "device_code": authorization.device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            if isinstance(token, str) and token.strip():
                return token.strip()
            error = data.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
                continue
            if error == "expired_token":
                raise AuthenticationError(
                    "GitHub login expired. Run 'agr auth login' again."
                )
            if error == "access_denied":
                raise AuthenticationError("GitHub login was cancelled or denied.")
            if isinstance(error, str):
                description = data.get("error_description")
                if isinstance(description, str) and description.strip():
                    raise AuthenticationError(description.strip())
                raise AuthenticationError(f"GitHub login failed: {error}")
            raise AuthenticationError("GitHub login failed: no access token returned.")
        raise AuthenticationError("GitHub login expired. Run 'agr auth login' again.")
