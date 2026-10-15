"""
The HTTP layer. These functions read a request, call google.py or slack.py,
and shape a response. Nothing clever should live here.
"""

import secrets
from datetime import datetime
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import google, slack
from .errors import ApiError
from .models import GoogleCredential, SlackInstallation


# --- status ----------------------------------------------------------------


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def status(request):
    """What the frontend needs to know on page load."""
    credential = GoogleCredential.objects.filter(pk=1).first()
    installation = SlackInstallation.objects.filter(pk=1).first()
    return Response(
        {
            "google": {"connected": credential is not None},
            "slack": {
                "connected": installation is not None,
                "team": installation.team_name if installation else None,
            },
            # Lets the UI say "add your credentials to .env" instead of
            # sending you to a confusing error page at Google or Slack.
            "configured": {
                "google": bool(settings.GOOGLE_CLIENT_ID),
                "slack": bool(settings.SLACK_CLIENT_ID),
            },
        }
    )


# --- OAuth -----------------------------------------------------------------
#
# These four are plain Django views, not API views: the browser navigates to
# them directly, and they answer with redirects rather than JSON.


def google_auth(request):
    if not settings.GOOGLE_CLIENT_ID:
        return _back(error="GOOGLE_CLIENT_ID is missing from backend/.env")
    return HttpResponseRedirect(google.auth_url(_new_state(request, "google_state")))


def google_callback(request):
    if request.GET.get("error"):
        return _back(error="Google access was denied.")
    try:
        _check_state(request, "google_state", request.GET.get("state"))
        google.save_tokens(request.GET.get("code", ""))
    except ApiError as exc:
        return _back(error=exc.message)
    return _back(connected="Google")


def slack_auth(request):
    if not settings.SLACK_CLIENT_ID:
        return _back(error="SLACK_CLIENT_ID is missing from backend/.env")
    return HttpResponseRedirect(slack.install_url(_new_state(request, "slack_state")))


def slack_callback(request):
    if request.GET.get("error"):
        return _back(error="Slack installation was cancelled.")
    try:
        _check_state(request, "slack_state", request.GET.get("state"))
        team = slack.save_installation(request.GET.get("code", ""))
    except ApiError as exc:
        return _back(error=exc.message)
    return _back(connected=f"Slack ({team})")


# --- data ------------------------------------------------------------------


@api_view(["GET"])
def slack_channels(request):
    return Response(slack.list_channels())


@api_view(["GET", "POST"])
def events(request):
    if request.method == "GET":
        return Response(google.list_events())

    data = request.data if isinstance(request.data, dict) else {}
    title = str(data.get("title") or "").strip()
    description = str(data.get("description") or "").strip()
    start = str(data.get("start") or "").strip()
    end = str(data.get("end") or "").strip()
    channel_id = str(data.get("channelId") or "").strip()

    raw_attendees = data.get("attendees") or []
    if isinstance(raw_attendees, str):
        raw_attendees = raw_attendees.split(",")
    attendees = [str(a).strip() for a in raw_attendees if str(a).strip()]

    # Cheap local checks first, before anything irreversible happens.
    if not title:
        raise ApiError("Please give the event a title.")
    if not start or not end:
        raise ApiError("Please give the event a start time and an end time.")
    if _parse(end) <= _parse(start):
        raise ApiError("The end time must be after the start time.")
    for email in attendees:
        if "@" not in email:
            raise ApiError(f"'{email}' does not look like an email address.")

    # Step 1: the irreversible step. Emails go out here. If it fails we stop,
    # because there is nothing to announce.
    event = google.create_event(title, description, start, end, attendees)

    # Step 2: announce it. notify_event() reports problems rather than
    # raising, so a failed Slack message cannot undo a real calendar event.
    if channel_id:
        slack_result = slack.notify_event(event, channel_id)
    else:
        slack_result = {"status": "skipped", "error": "No Slack channel selected."}

    return Response({"event": event, "slack": slack_result}, status=201)


# --- small helpers ---------------------------------------------------------


def _new_state(request, key):
    """
    Create an unguessable value and remember it in the session.

    Without this, somebody could send their own ?code= to our callback and
    connect THEIR account to YOUR session.
    """
    state = secrets.token_urlsafe(24)
    request.session[key] = state
    return state


def _check_state(request, key, given):
    """Reject any callback we did not start ourselves."""
    expected = request.session.pop(key, None)
    if not expected or not given or not secrets.compare_digest(expected, given):
        raise ApiError("Invalid OAuth state. Please start again.", 400)


def _back(**params):
    """Send the browser back to the React app with a short message."""
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/?{urlencode(params)}")


def _parse(value):
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ApiError(f"'{value}' is not a valid date and time.")
