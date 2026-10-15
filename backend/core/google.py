"""
Everything that talks to Google: the OAuth flow, and the two Calendar API
calls this app needs.

Reference:
  https://developers.google.com/identity/protocols/oauth2/web-server
  https://developers.google.com/calendar/api/v3/reference/events
"""

from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from .errors import ApiError
from .models import GoogleCredential

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# The smallest scope that lets us both read and create events. The broader
# ".../auth/calendar" would also allow deleting whole calendars.
SCOPE = "https://www.googleapis.com/auth/calendar.events"

TIMEOUT = 15


def auth_url(state):
    """Build the Google consent page URL we send the user to."""
    return AUTH_URL + "?" + urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",  # please send a refresh token
            "prompt": "consent",  # ...every time, not only on first consent
            "state": state,
        }
    )


def save_tokens(code):
    """
    Swap the one-time code for tokens.

    This request is the reason a backend exists: it carries our client
    secret, which a browser could never keep private.
    """
    response = requests.post(
        TOKEN_URL,
        timeout=TIMEOUT,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    if response.status_code != 200:
        raise ApiError(_error_message(response), 502)

    data = response.json()
    existing = GoogleCredential.objects.filter(pk=1).first()

    GoogleCredential.objects.update_or_create(
        pk=1,
        defaults={
            "access_token": data["access_token"],
            # Google sends a refresh token only on first consent. Never
            # overwrite a working one with nothing.
            "refresh_token": (
                data.get("refresh_token")
                or (existing.refresh_token if existing else "")
            ),
            "expires_at": timezone.now()
            + timedelta(seconds=data.get("expires_in", 3600)),
        },
    )


def _access_token():
    """Return a token valid right now, refreshing it if it is about to expire."""
    cred = GoogleCredential.objects.filter(pk=1).first()
    if cred is None:
        raise ApiError("Google is not connected yet.", 409)

    # Refresh a minute early: clocks drift and requests take time.
    if cred.expires_at <= timezone.now() + timedelta(seconds=60):
        response = requests.post(
            TOKEN_URL,
            timeout=TIMEOUT,
            data={
                "refresh_token": cred.refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code != 200:
            # The refresh token is dead - revoked, or expired because the
            # consent screen is in Testing mode. Retrying cannot help, so
            # forget it and ask the user to reconnect.
            cred.delete()
            raise ApiError(
                "Google access has expired. Please connect Google again.", 409
            )

        data = response.json()
        cred.access_token = data["access_token"]
        cred.expires_at = timezone.now() + timedelta(
            seconds=data.get("expires_in", 3600)
        )
        cred.save()

    return cred.access_token


def list_events(limit=10):
    """The next few upcoming events on the user's primary calendar."""
    response = requests.get(
        EVENTS_URL,
        timeout=TIMEOUT,
        headers={"Authorization": f"Bearer {_access_token()}"},
        params={
            "timeMin": timezone.now().isoformat(),
            "maxResults": limit,
            "singleEvents": "true",  # expand recurring events into occurrences
            "orderBy": "startTime",  # only allowed alongside singleEvents
        },
    )
    if response.status_code != 200:
        raise ApiError(_error_message(response), 502)

    return [_simplify(item) for item in response.json().get("items", [])]


def create_event(title, description, start, end, attendees):
    """Create an event and email the attendees."""
    body = {
        "summary": title,  # Google calls the title "summary"
        "description": description,
        "start": {
            "dateTime": _with_seconds(start),
            "timeZone": settings.CALENDAR_TIMEZONE,
        },
        "end": {
            "dateTime": _with_seconds(end),
            "timeZone": settings.CALENDAR_TIMEZONE,
        },
        "attendees": [{"email": email} for email in attendees],
    }

    response = requests.post(
        EVENTS_URL,
        timeout=TIMEOUT,
        json=body,
        headers={"Authorization": f"Bearer {_access_token()}"},
        # Without this nobody is emailed: the default is "none".
        params={"sendUpdates": "all"},
    )
    if response.status_code not in (200, 201):
        raise ApiError(_error_message(response), 502)

    return _simplify(response.json())


# --- small helpers ---------------------------------------------------------


def _with_seconds(value):
    """The browser sends "2026-10-20T15:00"; Google wants seconds as well."""
    return value + ":00" if len(value) == 16 else value


def _simplify(item):
    """Hand the frontend our own small shape rather than Google's full one."""
    start = item.get("start", {})
    end = item.get("end", {})
    return {
        "id": item.get("id", ""),
        "title": item.get("summary") or "(no title)",
        "description": item.get("description", ""),
        # All-day events carry "date" instead of "dateTime".
        "start": start.get("dateTime") or start.get("date", ""),
        "end": end.get("dateTime") or end.get("date", ""),
        "allDay": "date" in start,
        "link": item.get("htmlLink", ""),
        "attendees": [a.get("email", "") for a in item.get("attendees", [])],
    }


def _error_message(response):
    """Pull the useful sentence out of a Google error response."""
    try:
        return "Google says: " + response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return f"Google returned HTTP {response.status_code}."
