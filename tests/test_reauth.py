from unittest.mock import patch

from portfolio_agent.integrations.schwab_auth import build_authorization_url
from portfolio_agent.reauth_handler import callback_handler, reminder_handler


def test_authorization_url_contains_state():
    with patch(
        "portfolio_agent.integrations.schwab_auth.validate_config",
        return_value={
            "client_id": "client id",
            "client_secret": "secret",
            "callback_url": "https://example.com/callback",
        },
    ):
        url = build_authorization_url(state="state-value")

    assert "client_id=client%20id" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in url
    assert "state=state-value" in url


def test_callback_rejects_missing_or_invalid_state():
    with patch("portfolio_agent.reauth_handler.consume_state", return_value=False):
        response = callback_handler(
            {"queryStringParameters": {"code": "code", "state": "invalid"}},
            None,
        )

    assert response["statusCode"] == 400
    assert "expired" in response["body"]


def test_reminder_sends_recovery_link_after_expiration():
    expired = {"refresh_token_created_at": 1}
    with (
        patch("portfolio_agent.integrations.schwab_auth.load_tokens", return_value=expired),
        patch(
            "portfolio_agent.integrations.schwab_auth.refresh_token_is_valid",
            return_value=False,
        ),
        patch("portfolio_agent.reauth_handler.reminder_was_sent", return_value=False),
        patch("portfolio_agent.reauth_handler.create_state", return_value="state"),
        patch("portfolio_agent.reauth_handler.build_authorization_url", return_value="https://example.com/auth"),
        patch("portfolio_agent.reauth_handler.SESEmailSender") as sender_class,
        patch("portfolio_agent.reauth_handler.mark_reminder_sent") as mark_sent,
    ):
        response = reminder_handler({}, None)

    assert response == {"status": "sent"}
    sender_class.return_value.send.assert_called_once()
    mark_sent.assert_called_once_with(1)


def test_reminder_sends_recovery_link_when_token_metadata_is_missing():
    with (
        patch("portfolio_agent.integrations.schwab_auth.load_tokens", return_value=None),
        patch("portfolio_agent.reauth_handler.reminder_was_sent", return_value=False),
        patch("portfolio_agent.reauth_handler.create_state", return_value="state"),
        patch("portfolio_agent.reauth_handler.build_authorization_url", return_value="https://example.com/auth"),
        patch("portfolio_agent.reauth_handler.SESEmailSender") as sender_class,
        patch("portfolio_agent.reauth_handler.mark_reminder_sent") as mark_sent,
    ):
        response = reminder_handler({}, None)

    assert response == {"status": "sent"}
    sender_class.return_value.send.assert_called_once()
    mark_sent.assert_called_once()
