# Google Calendar + Slack — MVP

A small web app that connects Google Calendar and Slack. Connect both accounts,
see your upcoming events, create a new event, and have it announced in a Slack
channel.

Deliberately minimal: one Django app, SQLite, one React page. About 900 lines
in total.

Long explanations of how all of this works live in [`docs/`](docs/) — start with
[docs/00-start-here.md](docs/00-start-here.md).

---

## What works

- Google OAuth 2.0 with `state` validation and automatic token refresh
- Slack OAuth v2, storing the bot token and workspace
- List the next 10 upcoming events
- Create an event with title, description, start, end and attendees (who get
  emailed)
- Post the new event to a Slack channel you pick
- Three honest outcomes: created and posted, created but Slack failed, or
  nothing created

---

## Run it

Two terminals.

```powershell
# Terminal 1 - backend
cd backend
.\venv\Scripts\activate
python manage.py runserver 8010

# Terminal 2 - frontend
cd frontend
npm run dev
```

Then open <http://localhost:5173>.

> **Why 8010 and not Django's default 8000?** Another service on this machine
> already owns port 8000. The port appears in three places that must agree:
> `backend/.env` (the two redirect URIs), `frontend/src/api.ts`, and the URIs
> you register with Google and Slack. If you change it, change all four.

The virtualenv, `npm install` and the database migration are already done. If
you ever need to redo them:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate

cd ..\frontend
npm install
```

---

## Connect Google (needed before anything works)

Both buttons say "Add credentials to backend/.env" until you do this. All free.

1. **Create a project** at <https://console.cloud.google.com> — any name.

2. **Enable the API:** APIs & Services → Library → search `Google Calendar API`
   → Enable. Skipping this gives a confusing 403 *after* a successful login.

3. **OAuth consent screen:** APIs & Services → OAuth consent screen
   - User type **External**
   - Fill in the app name and your email
   - **Add your own Google address under Test users.** Without this you get
     `Error 403: access_denied`.

4. **Create credentials:** APIs & Services → Credentials → Create Credentials →
   OAuth client ID → **Web application**
   - Authorized redirect URI, copied exactly:
     ```
     http://localhost:8010/api/google/callback/
     ```
     The trailing slash matters. So does `localhost` rather than `127.0.0.1`.
     A mismatch gives `Error 400: redirect_uri_mismatch`, which is the most
     common thing to go wrong here.

5. Put the Client ID and Client Secret into `backend/.env`, and set your
   timezone:
   ```
   GOOGLE_CLIENT_ID=1234-abc.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-...
   CALENDAR_TIMEZONE=Asia/Kolkata
   ```

6. **Restart Django.** `.env` is only read at startup.

When you click Connect, Google shows a full-page "Google hasn't verified this
app" warning. That is expected for a development app — click **Advanced**, then
**Go to (app name) (unsafe)**.

---

## Connect Slack

1. **Create an app:** <https://api.slack.com/apps> → Create New App → **From
   scratch**. Pick a workspace you are allowed to install apps into — if yours
   is restricted, make a free one at <https://slack.com/create>.

2. **OAuth & Permissions:**
   - Redirect URL:
     ```
     http://localhost:8010/api/slack/callback/
     ```
     Then **click Save URLs** — easy to miss, and skipping it causes a redirect
     mismatch while the page looks correct.
   - Under **Bot** Token Scopes, add: `channels:read`, `chat:write`,
     `chat:write.public`
   - Do **not** click "Install to Workspace" — the app's own Connect button does
     that, which is the point.

3. Copy the Client ID and Client Secret from **Basic Information** into
   `backend/.env`:
   ```
   SLACK_CLIENT_ID=1234567890.9876543210
   SLACK_CLIENT_SECRET=...
   ```

4. **Restart Django.**

---

## The API

```
GET  /api/health/              {"status": "ok"}
GET  /api/status/              what is connected, and what is configured

GET  /api/google/auth/         redirects to Google's consent screen
GET  /api/google/callback/     Google sends the user back here
GET  /api/slack/auth/          redirects to Slack's install page
GET  /api/slack/callback/      Slack sends the user back here

GET  /api/slack/channels/      [{"id": "C04...", "name": "general"}]
GET  /api/events/              the next 10 upcoming events
POST /api/events/              create an event, then announce it in Slack
```

Testing with curl (in PowerShell use `curl.exe`, not `curl`):

```bash
curl http://localhost:8010/api/health/
curl http://localhost:8010/api/events/

curl -X POST http://localhost:8010/api/events/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Design review",
       "description":"Walk through the new flow",
       "start":"2026-10-20T15:00",
       "end":"2026-10-20T16:00",
       "attendees":["teammate@example.com"],
       "channelId":"C04IJKLMNOP"}'
```

`POST /api/events/` returns all three outcomes distinctly:

```jsonc
// created, and announced
{ "event": {...}, "slack": { "status": "sent" } }

// created, but Slack failed - still 201, because the event is real
{ "event": {...}, "slack": { "status": "failed",
                             "error": "The Slack app is missing a permission..." } }

// nothing created - 502, and no Slack message was attempted
{ "error": "Google says: ..." }
```

---

## Where the code is

```
backend/
  config/settings.py    the only file that reads environment variables
  core/models.py        GoogleCredential, SlackInstallation
  core/google.py        OAuth, token refresh, list and create events
  core/slack.py         OAuth, list channels, post message
  core/views.py         the HTTP layer - reads requests, shapes responses
  core/errors.py        one error type, turned into clean JSON
  .env                  your secrets (git ignores this)
  .env.example          the same keys with placeholder values

frontend/
  src/api.ts            the only file that knows the backend's URLs
  src/App.tsx           the whole UI
  src/index.css         styles
```

Three things in there are worth a look if you read nothing else:

- **`core/views.py`, the `events()` function** — validate locally first, create
  in Google second (the irreversible step), announce in Slack last. If Google
  fails, no Slack message is attempted, because there is nothing to announce.
- **`core/slack.py`, the `_call()` function** — every Slack request goes through
  it because Slack returns HTTP 200 even when it failed, and puts the truth in
  an `ok` field. Checking the status code alone would report success for every
  failure.
- **`core/google.py`, the `_access_token()` function** — refreshes the token a
  minute before it expires, and never overwrites a good refresh token with
  nothing.

---

## Shortcuts taken, and what they would become

This is a local demo. What is already done properly: secrets in `.env` and out
of git, nothing sensitive in the frontend, `state` validation on both OAuth
flows, minimum scopes, and no credentials in any log.

What is not, and why:

| Shortcut | For production |
|---|---|
| Tokens stored as plain text | Encrypt at rest, key in a secret manager |
| `DEBUG = True` | `False`, with `ALLOWED_HOSTS` set |
| HTTP on localhost | HTTPS, plus secure/HttpOnly cookie settings |
| One user, no login | Real auth, and a user foreign key on both token tables |
| Slack posted synchronously, no retry | A background queue with backoff |
| Duplicate posts prevented only by disabling the button | A `UNIQUE (event_id, channel_id)` table row claimed before posting |
| SQLite | PostgreSQL |
| No tests | Tests for the failure paths, with third-party HTTP mocked |

[docs/10-security-notes.md](docs/10-security-notes.md) goes through each of
these properly. [docs/06-connecting-both.md](docs/06-connecting-both.md)
explains the duplicate-prevention one, which is the most interesting.

---

## When something breaks

[docs/12-troubleshooting.md](docs/12-troubleshooting.md) covers the errors you
are likely to hit. The three that catch everyone:

- **`redirect_uri_mismatch`** — the URI in `.env` and the one registered with
  the provider differ. Check the trailing slash.
- **`invalid_grant` after it worked yesterday** — Google expires refresh tokens
  after 7 days while the consent screen is in Testing mode. Click Connect again;
  it is not a bug in the code.
- **Changed `.env` and nothing happened** — restart Django. It reads `.env` only
  at startup.
