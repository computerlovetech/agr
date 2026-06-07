import httpx
import pytest

from agr.auth import DeviceAuthorization
from agr.exceptions import AuthenticationError
from agr.github_oauth import (
    GITHUB_ACCESS_TOKEN_URL,
    GITHUB_DEVICE_CODE_URL,
    GitHubOAuthDeviceFlow,
    MISSING_CLIENT_ID_MESSAGE,
    UNCONFIGURED_GITHUB_OAUTH_CLIENT_ID,
)


def make_client(
    responses: list[dict[str, object]],
) -> tuple[httpx.Client, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=responses.pop(0))

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_request_device_authorization_requires_configured_client_id() -> None:
    flow = GitHubOAuthDeviceFlow(client_id=UNCONFIGURED_GITHUB_OAUTH_CLIENT_ID)

    with pytest.raises(AuthenticationError, match="not configured"):
        flow.request_device_authorization()

    assert "AGR_GITHUB_OAUTH_CLIENT_ID" in MISSING_CLIENT_ID_MESSAGE


def test_uses_client_id_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGR_GITHUB_OAUTH_CLIENT_ID", "env-client-id")
    client, requests = make_client(
        [
            {
                "device_code": "device-code",
                "user_code": "USER-CODE",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }
        ]
    )
    flow = GitHubOAuthDeviceFlow(client_id="client-id", client=client)

    flow.request_device_authorization()

    assert "client_id=env-client-id" in requests[0].content.decode()


def test_request_device_authorization_raises_friendly_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    flow = GitHubOAuthDeviceFlow(client_id="client-id", client=client)

    with pytest.raises(AuthenticationError, match="HTTP 404"):
        flow.request_device_authorization()


def test_request_device_authorization_returns_caller_facing_data() -> None:
    client, requests = make_client(
        [
            {
                "device_code": "device-code",
                "user_code": "USER-CODE",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }
        ]
    )
    flow = GitHubOAuthDeviceFlow(client_id="client-id", client=client)

    authorization = flow.request_device_authorization()

    assert authorization == DeviceAuthorization(
        device_code="device-code",
        user_code="USER-CODE",
        verification_uri="https://github.com/login/device",
        expires_in=900,
        interval=5,
    )
    assert str(requests[0].url) == GITHUB_DEVICE_CODE_URL
    assert "client_id=client-id" in requests[0].content.decode()


def test_poll_for_token_handles_pending_then_success() -> None:
    client, requests = make_client(
        [
            {"error": "authorization_pending"},
            {"access_token": " github-token "},
        ]
    )
    sleeps: list[float] = []
    flow = GitHubOAuthDeviceFlow(
        client_id="client-id", client=client, sleep=sleeps.append
    )

    token = flow.poll_for_token(DeviceAuthorization("device", "USER", "url", 900, 1))

    assert token == "github-token"
    assert sleeps == [1, 1]
    assert [str(request.url) for request in requests] == [
        GITHUB_ACCESS_TOKEN_URL,
        GITHUB_ACCESS_TOKEN_URL,
    ]


def test_poll_for_token_handles_slow_down() -> None:
    client, _ = make_client(
        [
            {"error": "slow_down"},
            {"access_token": "github-token"},
        ]
    )
    sleeps: list[float] = []
    flow = GitHubOAuthDeviceFlow(
        client_id="client-id", client=client, sleep=sleeps.append
    )

    assert (
        flow.poll_for_token(DeviceAuthorization("device", "USER", "url", 900, 2))
        == "github-token"
    )
    assert sleeps == [2, 7]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        ("expired_token", "expired"),
        ("access_denied", "cancelled|denied"),
    ],
)
def test_poll_for_token_raises_for_terminal_errors(error: str, message: str) -> None:
    client, _ = make_client([{"error": error}])
    flow = GitHubOAuthDeviceFlow(
        client_id="client-id", client=client, sleep=lambda _: None
    )

    with pytest.raises(AuthenticationError, match=message):
        flow.poll_for_token(DeviceAuthorization("device", "USER", "url", 900, 1))


def test_poll_for_token_raises_for_unknown_error_description() -> None:
    client, _ = make_client(
        [{"error": "bad_verification_code", "error_description": "Bad code"}]
    )
    flow = GitHubOAuthDeviceFlow(
        client_id="client-id", client=client, sleep=lambda _: None
    )

    with pytest.raises(AuthenticationError, match="Bad code"):
        flow.poll_for_token(DeviceAuthorization("device", "USER", "url", 900, 1))
