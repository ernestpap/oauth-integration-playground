# 08 — Accounts and Setup

This document is the click-by-click guide to the external accounts. It is
reference material — you do not need to do any of it now. I will tell you when
each part is needed, and we will walk through it together.

Your machine is already ready. I checked:

```
Python   3.12.10     ✓
Node     26.7.0      ✓
npm      11.19.0     ✓
git      2.55.0      ✓
```

Nothing to install at the language level.

---

## Part 1: Google Cloud — needed for Phase 2

Everything here is free. The Calendar API has a generous free quota that a
learning project will not come close to.

### Step 1: Pick a Google account to test with

Use a throwaway or personal Google account rather than a work one if you can.

Two reasons. You will be granting and revoking calendar access repeatedly, and
creating test events — nicer not to do that in a calendar other people look at.
And some organisations restrict which third-party apps their accounts may
authorise, which can block you with an error that looks like a bug in your code.

### Step 2: Create a Google Cloud project

1. Go to https://console.cloud.google.com
2. Click the project dropdown at the top of the page.
3. Click **New Project**.
4. Name it something recognisable, such as `calendar-slack-demo`.
5. Click **Create**, then wait a few seconds and make sure the project selector
   at the top now shows your new project.

A "project" here is just a container for API settings and credentials. It is not
code and it does not cost anything.

### Step 3: Enable the Google Calendar API

This step is easy to forget, and forgetting it produces an error message that
does not obviously point at it.

1. In the left menu, go to **APIs & Services → Library**.
2. Search for `Google Calendar API`.
3. Click it, then click **Enable**.

If you skip this, your OAuth flow will work perfectly, you will receive valid
tokens, and then your very first API call will fail with:

```json
{ "error": { "code": 403,
             "message": "Google Calendar API has not been used in project
                         123456 before or it is disabled." } }
```

The message is actually clear once you read it carefully. The confusion comes
from it appearing *after* a successful login, which makes it feel like a token
problem rather than a setup problem.

### Step 4: Configure the OAuth consent screen

This is what the user sees when they click Allow. It must be configured before
you can create credentials.

1. Go to **APIs & Services → OAuth consent screen**.
2. Choose **External** as the user type, then **Create**.
   - *Internal* is only available with a Google Workspace organisation account,
     and limits the app to that organisation.
3. Fill in the required fields:
   - **App name**: `Calendar Slack Demo` — this is the name users will see on
     the consent screen, so make it something you will recognise.
   - **User support email**: your address.
   - **Developer contact email**: your address.
4. Save and continue.
5. On the **Scopes** step you can skip adding scopes. We request them in our
   authorize URL instead; this screen is for the verification process.
6. On the **Test users** step, click **Add Users** and **add your own Google
   email address**.

### Step 5: Understand "Testing" mode, because it will affect you

Your app is now in **Testing** publishing status. Three consequences you should
know about in advance, so that when they happen you recognise them instead of
debugging them.

**Only listed test users can authorise the app.** If you try with an account not
on the list, you get `Error 403: access_denied` and "app is in testing mode." The
fix is to add that account to Test users.

**Google shows an "unverified app" warning.** A full-page interstitial saying
"Google hasn't verified this app." Click **Advanced**, then **Go to Calendar
Slack Demo (unsafe)**. This is expected. Published apps requesting sensitive
scopes go through a review process to remove it, which involves a privacy policy,
a demo video and a few weeks of waiting. Not something to do for a learning
project.

**Refresh tokens expire after seven days.** This is the one that will catch you
mid-project. In Testing mode, Google invalidates refresh tokens a week after
issue. So you will come back to the project after a break, and your perfectly
correct code will fail with `invalid_grant`.

This is not your bug. The fix is to click Connect Google again. I am telling you
now so that you do not spend an hour hunting for a fault in your refresh logic
that is not there.

There is a silver lining: it guarantees you will exercise your "reconnect
required" error path for real, which most tutorials never do.

### Step 6: Create the OAuth client credentials

1. Go to **APIs & Services → Credentials**.
2. Click **Create Credentials → OAuth client ID**.
3. **Application type: Web application.** This matters — it is the type that gets
   a client secret, which is what our backend flow requires.
4. Name it something like `calendar-slack-demo-local`.
5. Under **Authorized redirect URIs**, click **Add URI** and enter exactly:

```
http://localhost:8000/api/google/oauth/callback/
```

Please copy that character for character. Document 04 explains why, but to
restate it: the trailing slash matters, `http` versus `https` matters,
`localhost` versus `127.0.0.1` matters, and capitalisation matters. A mismatch
produces `Error 400: redirect_uri_mismatch`, which is the most common thing to go
wrong in this project.

You do not need to add anything under *Authorized JavaScript origins*. That field
is for browser-based flows, and ours is a backend flow.

6. Click **Create**. A dialog appears with your **Client ID** and **Client
   secret**.
7. Copy both. The client secret can be viewed again later from the same page, so
   this is not your only chance, but copy it now anyway.

These go into `backend/.env` in Phase 2:

```
GOOGLE_CLIENT_ID=1234567890-abcdefghijk.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-YOUR-CLIENT-SECRET
```

### Google checklist

- [ ] Cloud project created and selected
- [ ] Google Calendar API enabled
- [ ] OAuth consent screen configured, External, with an app name
- [ ] Your own email added under Test users
- [ ] OAuth client ID created, type Web application
- [ ] Redirect URI added exactly as `http://localhost:8000/api/google/oauth/callback/`
- [ ] Client ID and Client secret copied somewhere safe

---

## Part 2: Slack — needed for Phase 3

Also free.

### Step 1: Make sure you have a workspace you can install apps into

This is worth checking **now**, not in Phase 3, because it is the one prerequisite
that might need somebody else's permission.

Many companies restrict app installation to administrators. If your work
workspace does, you will get stuck at the install step with a message about
needing approval.

The quick way to find out: go to https://api.slack.com/apps and see whether you
can create an app and whether your workspace appears in the dropdown.

If it is restricted, create a free personal workspace at
https://slack.com/create. It takes about two minutes, you will be its
administrator, and it is a better place to experiment anyway.

### Step 2: Create the Slack app

1. Go to https://api.slack.com/apps
2. Click **Create New App**.
3. Choose **From scratch**. (The "From an app manifest" option would let you
   paste in a YAML configuration — faster, but it would hide the settings we are
   trying to understand.)
4. **App Name**: `Calendar Demo`. This is the name that will appear next to
   messages in Slack.
5. Pick the workspace to develop in.
6. Click **Create App**.

### Step 3: Configure OAuth and permissions

1. In the left menu, click **OAuth & Permissions**.

2. Scroll to **Redirect URLs**. Click **Add New Redirect URL** and enter exactly:

```
http://localhost:8000/api/slack/oauth/callback/
```

3. **Click Add, and then click Save URLs.**

   That second button is easy to miss, and if you miss it the URL is not actually
   saved. You then get a redirect mismatch error while looking at a screen that
   appears to show the correct URL. If you hit a mismatch error during Phase 3,
   come back and check this first.

4. Scroll down to **Scopes → Bot Token Scopes**. Click **Add an OAuth Scope** and
   add these three, one at a time:

```
channels:read          read the list of public channels
chat:write             post messages
chat:write.public      post to public channels without being invited first
```

   Make sure you are adding them under **Bot** Token Scopes, not User Token
   Scopes. Document 05 explains the difference; adding them in the wrong place is
   a confusing failure because the install succeeds and then every call reports
   `missing_scope`.

5. **Do not click "Install to Workspace."**

   There is a prominent button at the top of this page offering to install the
   app and hand you a token. Clicking it would skip the entire exercise. We are
   going to install the app through our own OAuth flow in Phase 3, because
   building that flow is the point.

### Step 4: Copy the credentials

1. In the left menu, click **Basic Information**.
2. Scroll to **App Credentials**.
3. Copy the **Client ID** and the **Client Secret** (click Show to reveal it).

These go into `backend/.env`:

```
SLACK_CLIENT_ID=1234567890.9876543210
SLACK_CLIENT_SECRET=YOUR-SLACK-CLIENT-SECRET
```

You will also see a **Signing Secret** on that page. We do not need it. It is for
verifying that incoming requests from Slack are genuine, which matters when your
app *receives* events from Slack. Ours only sends.

### Step 5: Optional but recommended — give the bot a face

On **Basic Information**, under *Display Information*, you can set an icon and a
background colour. Purely cosmetic, but it makes your notifications look
deliberate rather than broken, and it is quite satisfying to see your own bot
appear in a channel.

### Step 6: Create a test channel

In your Slack workspace, create a channel called `#demo-notifications`.

Posting test messages into `#general` while you iterate is a good way to annoy
people, including yourself.

### Slack checklist

- [ ] A workspace where you are allowed to install apps
- [ ] Slack app created from scratch
- [ ] Redirect URL added **and saved** as `http://localhost:8000/api/slack/oauth/callback/`
- [ ] Bot Token Scopes added: `channels:read`, `chat:write`, `chat:write.public`
- [ ] Did **not** click Install to Workspace
- [ ] Client ID and Client Secret copied somewhere safe
- [ ] `#demo-notifications` channel created

---

## Part 3: Local setup — Phase 1

We will do all of this together in Phase 1. It is listed here for completeness.

### Git, initialised before anything else exists

```powershell
cd "D:\work\learn by doing"
git init
```

And then, immediately, `.gitignore` — before `.env` is ever created. Document 07
explains why that order matters: a secret that is committed once stays in git
history forever, and the only real remedy is to revoke the secret.

### The Python virtual environment

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
```

A virtual environment is a private copy of Python's package directory for this
project alone. Without one, `pip install` puts packages into your system Python,
and two projects wanting different versions of the same library start breaking
each other.

You can tell it is active because your prompt gains a `(venv)` prefix. It needs
activating in each new terminal you open.

### Python packages

```
django
djangorestframework
django-cors-headers
python-dotenv
requests
cryptography
pytest
pytest-django
responses
```

What each is for:

| Package | Why |
|---|---|
| `django` | The web framework |
| `djangorestframework` | JSON API building blocks on top of Django |
| `django-cors-headers` | Lets us allow requests from `localhost:5173` |
| `python-dotenv` | Reads `.env` into environment variables |
| `requests` | Makes HTTP calls to Google and Slack |
| `cryptography` | Provides Fernet, which encrypts the stored tokens |
| `pytest`, `pytest-django` | Test runner |
| `responses` | Fakes HTTP responses in tests, so tests never call the real Google or Slack |

That last one is worth noticing now. It is how we will test "what happens when
Google returns a 403" — you cannot ask Google to fail on request, so you fake its
reply.

### Frontend packages

Created with Vite's scaffolding:

```powershell
cd frontend
npm create vite@latest . -- --template react-ts
npm install
```

### Generating the two random secrets

Two values in `.env` need to be random rather than chosen. We will generate them
properly in Phase 1:

```powershell
# Django's secret key, used for signing session cookies
python -c "import secrets; print(secrets.token_urlsafe(50))"

# The Fernet key used to encrypt tokens before storing them
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

One important warning about the Fernet key: **if you lose or change it, every
token already in your database becomes undecryptable.** They are not recoverable.
In this project the consequence is mild — click Connect again and new tokens are
stored — but in a real system, key rotation is something you plan for rather than
discover.

---

## Part 4: Testing tools

You will test your API with `curl` before any user interface exists.

`curl` ships with Windows 10 and 11, so you already have it. One wrinkle worth
knowing: in PowerShell, `curl` is an alias for `Invoke-WebRequest`, which takes
different arguments. To get the real thing, use `curl.exe`:

```powershell
curl.exe http://localhost:8000/api/health/
```

Or use the Bash shell, where `curl` is just `curl`.

If you prefer a graphical tool, Postman (https://www.postman.com/downloads/) is
fine and makes it easier to save requests for re-use. Either works.

---

## Part 5: Secrets summary

The complete list of sensitive values you will hold, where each may appear, and
where it must never appear.

| Secret | Lives in | Never in |
|---|---|---|
| `GOOGLE_CLIENT_SECRET` | `backend/.env` | frontend, git, logs, URLs |
| `SLACK_CLIENT_SECRET` | `backend/.env` | frontend, git, logs, URLs |
| `TOKEN_ENCRYPTION_KEY` | `backend/.env` | anywhere else, ever |
| `DJANGO_SECRET_KEY` | `backend/.env` | anywhere else |
| Google access token | database, encrypted | logs, API responses, frontend |
| Google refresh token | database, encrypted | logs, API responses, frontend |
| Slack bot token | database, encrypted | logs, API responses, frontend |

And the non-secrets, which are safe in public:

| Value | Why it is fine |
|---|---|
| `GOOGLE_CLIENT_ID` | A public identifier. It appears in a URL the browser visits |
| `SLACK_CLIENT_ID` | Same |
| Redirect URIs | Public addresses, and the provider enforces the whitelist |
| `VITE_API_BASE_URL` | Just our own backend's address |

Look at the frontend column in that first table. It is empty for every row. That
is the whole security model in one observation.

---

Next: [09 — Implementation Plan](09-implementation-plan.md)
