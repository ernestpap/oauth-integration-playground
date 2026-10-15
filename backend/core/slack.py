"""
Everything that talks to Slack.

Reference:
  https://api.slack.com/authentication/oauth-v2
  https://api.slack.com/methods/conversations.list
  https://api.slack.com/methods/chat.postMessage
"""

from urllib.parse import urlencode

import requests
from django.conf import settings

from .errors import ApiError
from .models import SlackInstallation

AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
API_URL = "https://slack.com/api/"

# channels:read      read the list of public channels
# chat:write         post messages
# chat:write.public  post to a public channel without being invited first
SCOPES = "channels:read,chat:write,chat:write.public"

TIMEOUT = 15

# Slack's error strings are precise but unhelpful to a user, so we
# translate the ones we expect into something actionable.
EXPLANATIONS = {
    "missing_scope": "The Slack app is missing a permission. Connect Slack again to grant it.",
    "not_in_channel": "The bot is not in that channel. Connect Slack again, or invite it with /invite.",
    "channel_not_found": "That channel does not exist, or this app cannot see it.",
    "is_archived": "That channel is archived. Please choose another one.",
    "invalid_auth": "The Slack token is no longer valid. Please connect Slack again.",
    "token_revoked": "The Slack app was uninstalled. Please connect Slack again.",
    "account_inactive": "The Slack bot was deactivated. Please connect Slack again.",
    "msg_too_long": "The message was too long for Slack.",
}


def install_url(state):
    """Build the Slack install page URL we send the user to."""
    return AUTHORIZE_URL + "?" + urlencode(
        {
            "client_id": settings.SLACK_CLIENT_ID,
            "scope": SCOPES,  # commas here; Google uses spaces
            "redirect_uri": settings.SLACK_REDIRECT_URI,
            "state": state,
        }
    )


def save_installation(code):
    """Swap the one-time code for a bot token and remember the workspace."""
    data = _call(
        "oauth.v2.access",
        form={
            "code": code,
            "client_id": settings.SLACK_CLIENT_ID,
            "client_secret": settings.SLACK_CLIENT_SECRET,
            "redirect_uri": settings.SLACK_REDIRECT_URI,
        },
    )
    team = data.get("team") or {}
    SlackInstallation.objects.update_or_create(
        pk=1,
        defaults={
            "bot_token": data["access_token"],
            "team_id": team.get("id", ""),
            "team_name": team.get("name", "your workspace"),
        },
    )
    return team.get("name", "your workspace")


def list_channels():
    """Every public channel, following pagination."""
    token = _token()
    channels = []
    cursor = ""

    while True:
        body = _call(
            "conversations.list",
            token=token,
            form={
                "types": "public_channel",
                "exclude_archived": "true",
                "limit": 200,
                "cursor": cursor,
            },
        )
        channels += [
            {"id": c["id"], "name": c["name"]} for c in body.get("channels", [])
        ]

        # A non-empty cursor means there is another page. Ignoring it is how
        # integrations quietly break in workspaces bigger than your own.
        cursor = (body.get("response_metadata") or {}).get("next_cursor", "")
        if not cursor:
            break

    channels.sort(key=lambda c: c["name"])
    return channels


def notify_event(event, channel_id):
    """
    Announce a newly created event in a Slack channel.

    Returns a small dict describing what happened, and never raises: by the
    time we get here the calendar event already exists, and a failed
    announcement must not turn a real success into an error response.
    """
    lines = [f"*New calendar event:* {event['title']}", _when(event)]
    if event.get("description"):
        lines.append(event["description"])
    if event.get("attendees"):
        lines.append(f"{len(event['attendees'])} attendee(s) invited")
    if event.get("link"):
        lines.append(f"<{event['link']}|Open in Google Calendar>")

    try:
        _call(
            "chat.postMessage",
            token=_token(),
            json_body={"channel": channel_id, "text": "\n".join(lines)},
        )
        return {"status": "sent"}
    except ApiError as exc:
        return {"status": "failed", "error": exc.message}
    except requests.RequestException:
        return {"status": "failed", "error": "Could not reach Slack."}


# --- small helpers ---------------------------------------------------------


def _call(method, token=None, form=None, json_body=None):
    """
    Every Slack request goes through here, for one reason: Slack answers
    with HTTP 200 even when it failed, and puts the truth in "ok". Checking
    the status code alone would report success for every kind of failure.
    """
    response = requests.post(
        API_URL + method,
        timeout=TIMEOUT,
        headers={"Authorization": f"Bearer {token}"} if token else {},
        data=form,
        json=json_body,
    )

    if response.status_code == 429:
        wait = response.headers.get("Retry-After", "a few")
        raise ApiError(f"Slack is rate limiting us. Try again in {wait} seconds.", 429)

    body = response.json()
    if not body.get("ok"):
        code = body.get("error", "unknown_error")
        raise ApiError(EXPLANATIONS.get(code, f"Slack says: {code}"), 502)

    return body


def _token():
    installation = SlackInstallation.objects.filter(pk=1).first()
    if installation is None:
        raise ApiError("Slack is not connected yet.", 409)
    return installation.bot_token


def _when(event):
    """"2026-10-20T15:00:00+05:30" -> "2026-10-20 at 15:00" """
    date_part, _, time_part = event.get("start", "").partition("T")
    if event.get("allDay") or not time_part:
        return f"{date_part} (all day)"
    return f"{date_part} at {time_part[:5]}"
