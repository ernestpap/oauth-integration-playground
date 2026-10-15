# 12 — Troubleshooting

Keep this one open while we build. It covers the errors you are statistically
likely to hit, in roughly the order you will hit them.

---

## First, how to debug rather than guess

Before the specific errors, the general method. This matters more than the list
below, because the list cannot contain everything.

When something breaks, the instinct is to change code and see if it helps. That
occasionally works and teaches you nothing, and more often it moves the bug
somewhere less obvious.

Try this instead.

**1. Read the actual error.** All of it, including the parts that look like
noise. Error messages are usually more specific than people give them credit
for. `redirect_uri_mismatch` is telling you exactly what is wrong.

**2. Work out which of the five places it happened.** Every bug in this project
is in one of:

```
the browser          →  check the browser console and network tab
our frontend code    →  check the network tab: what did we send?
our backend code     →  check the terminal running Django
the provider         →  check the response body they sent back
your configuration   →  check .env and the provider's dashboard
```

Knowing which one narrows your search enormously, and it is usually quick to
determine. Did the request leave the browser? Look at the network tab. Did it
reach Django? Look at the terminal log.

**3. Form one specific guess.** Not "something is wrong with the token" but "I
think the access token is expired and the refresh is not being triggered." A
vague guess cannot be tested.

**4. Check that guess with the smallest possible experiment.** Print the one
value. Call the one endpoint with `curl`. Query the one table.

**5. Only then change code.**

The reason this matters: at some point in this project you will spend half an
hour debugging the wrong file. Everybody does. The habit above is what shortens
that half hour, and it is the part of this project that transfers to every other
job you ever do.

One more thing. **When an error message contains a URL or a value, read it
carefully.** A surprising number of integration bugs are visible in the error
itself — a missing slash, a `127.0.0.1` where you expected `localhost`, a scope
spelled slightly wrong.

---

## Phase 1 problems

### `python: command not found` or the Microsoft Store opens

On your machine `python` works but `python3` does not — Windows has an app
execution alias that intercepts `python3` and offers to install from the Store.

Use `python`, not `python3`, throughout this project.

### `(venv)` does not appear in my prompt

The virtual environment is not activated. Each new terminal needs it:

```powershell
cd backend
.\venv\Scripts\activate
```

If PowerShell refuses with an execution policy error, either use the Bash shell
instead or allow local scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Symptom if you forget: `pip install` appears to work, and then Django is "not
found" when you try to run it — because you installed it somewhere else.

### CORS error in the browser console

```
Access to fetch at 'http://localhost:8000/api/health/' from origin
'http://localhost:5173' has been blocked by CORS policy
```

Four things to check, in order:

1. Is `corsheaders` in `INSTALLED_APPS`?
2. Is `CorsMiddleware` in `MIDDLEWARE`, and is it **above**
   `CommonMiddleware`? Order matters here, and the symptom of getting it wrong
   is identical to not having it at all.
3. Does `CORS_ALLOWED_ORIGINS` contain exactly `http://localhost:5173`, with no
   trailing slash?
4. **Did you restart Django?** Settings are read at startup.

That last one catches people repeatedly. If you changed `settings.py` or `.env`
and nothing happened, restart the server.

### My change to `.env` had no effect

`.env` is read once, when Django starts. Stop the server with `Ctrl+C` and start
it again.

### Frontend shows "Failed to fetch" with nothing in the network tab

The backend is not running, or is on a different port. Check the terminal where
you started it, and confirm the port in `VITE_API_BASE_URL`.

---

## Phase 2 problems — Google

### `Error 400: redirect_uri_mismatch`

**This will happen to you.** It is the most common error in the whole project.

Google is saying: the `redirect_uri` you sent is not one I have registered for
this client ID.

Compare these two values character by character:

- the value in your `.env` as `GOOGLE_REDIRECT_URI`
- the value in Google Cloud Console → Credentials → your OAuth client →
  Authorized redirect URIs

Things that make them different even when they look the same:

```
trailing slash present in one and not the other
http vs https
localhost vs 127.0.0.1
a different port
any difference in capitalisation
an invisible trailing space from a copy-paste
```

Useful trick: Google's error page includes the exact URI it received. Expand the
error detail and compare that against the Console. The answer is usually visible
right there.

Also worth knowing: changes to redirect URIs in the Console can take a minute or
two to propagate. If you have corrected it and it still fails, wait thirty
seconds and retry before concluding you were wrong.

### `Error 403: access_denied` — "app is in testing mode"

Your Google account is not on the Test users list.

Cloud Console → APIs & Services → OAuth consent screen → Test users → Add Users
→ your email address.

### "Google hasn't verified this app"

Expected. Click **Advanced**, then **Go to (app name) (unsafe)**.

This appears because our consent screen is unverified, which is the correct state
for a development app. Document 08 covers it, and document 10 explains what
verification would involve.

### My API call returns 403 `accessNotConfigured`

The Calendar API is not enabled for your Cloud project.

Cloud Console → APIs & Services → Library → Google Calendar API → Enable.

The confusing part is that this appears *after* a successful login, so it feels
like a token problem. It is not; it is a setup step. The error message does name
the project, which confirms it.

### I never receive a `refresh_token`

Three possible causes:

1. `access_type=offline` is missing from your authorize URL. Without it Google
   has no reason to issue one.
2. You have already consented before and `prompt=consent` is missing. Google
   issues a refresh token only on first consent. Revoke access at
   https://myaccount.google.com/permissions and try again, or add
   `prompt=consent`.
3. You received it and your storage code overwrote it. See the next entry.

### Everything worked yesterday and now I get `invalid_grant`

Most likely explanation, and it is not a bug in your code: **your OAuth consent
screen is in Testing mode, where Google expires refresh tokens after seven
days.**

The fix is to click Connect Google again.

Other possible causes:
- You revoked access at https://myaccount.google.com/permissions
- Your code overwrote the stored refresh token with `None`, because the refresh
  response does not include one. Check that your save logic only updates the
  refresh token when a new one is actually present.

### 401 `invalid_credentials` on every call

The access token is expired or malformed. Check in this order:

1. Is `expires_at` in the past? Then the refresh is not being triggered. Confirm
   your refresh check is actually being called before the API request.
2. Is the stored token being decrypted correctly? Print its length — an access
   token is long. A short or empty string means encryption or storage went wrong.
3. Is the header formatted as `Authorization: Bearer <token>`, with the space?

### 403 `insufficientPermissions`

The token is valid but its scope does not cover what you are attempting.

Usually this means you changed the scope in your code after connecting, and the
stored token predates the change. Tokens carry the scopes granted at the time
they were issued. Reconnect to get a token with the new scope.

### The event was created but nobody got an email

You did not pass `sendUpdates=all`. The default is `none`, which adds attendees
silently.

### My event list crashes on one particular event

Almost certainly an **all-day event**. Those have `start.date` instead of
`start.dateTime`. Handle both shapes.

### 400 `timeRangeEmpty` or a validation error on creation

The end time is at or before the start time, or a timestamp is not valid RFC
3339. Your own serializer should catch this before the request goes out, which is
why we validate first.

---

## Phase 3 problems — Slack

### `bad_redirect_uri` or a redirect mismatch

Same class of problem as Google's, with one extra Slack-specific cause: **you
added the redirect URL but did not click Save URLs.**

Go back to api.slack.com/apps → your app → OAuth & Permissions → Redirect URLs,
and check that the URL is actually saved. The button is easy to miss, and the
page looks correct either way.

### `invalid_scope` on the authorize URL

Check the separator. Slack wants **commas** between scopes; Google wants spaces.
Mixing them up produces this.

Also check the spelling. `chat:write.public` has a dot, not a colon, before
`public`.

### `missing_scope` on every call

The scope was not granted when the app was installed.

Important: **adding the scope to your app configuration is not enough.** The
token you already hold was issued with the old scope set and cannot gain
permissions. You must reinstall the app so the user consents again.

Check also that you added the scope under **Bot** Token Scopes rather than User
Token Scopes. The install succeeds either way, which makes this confusing — then
every call fails with `missing_scope` while the dashboard appears to show the
scope present.

The error response is helpful here:

```json
{ "ok": false, "error": "missing_scope",
  "needed": "channels:read", "provided": "chat:write" }
```

`needed` and `provided` tell you precisely what to fix.

### `not_in_channel`

The bot is not a member of that channel and does not have `chat:write.public`.

Either add that scope and reinstall, or type `/invite @YourApp` in the channel.

### `channel_not_found`

Either the ID is wrong, or the channel is private and your token cannot see it.

Check that you are sending the channel **ID** (`C04IJKLMNOP`) and not the name
(`#demo-notifications`). A name where an ID is expected produces exactly this
error.

### My code says the message sent, but nothing appeared in Slack

This is the `ok: false` trap from document 05.

Slack returned HTTP 200 with `{"ok": false, "error": "..."}` and your code only
checked the status code. Print the response body and you will see the real error.

Every Slack call must check `ok`. This is why we route all of them through one
function.

### HTTP 429 with `Retry-After`

You are rate limited. Wait the number of seconds in the header, then retry once.
Do not retry immediately, and do not loop.

If you hit this during development, you are probably calling
`conversations.list` on every render. Fetch it once.

### `invalid_blocks`

Your Block Kit JSON is malformed. Paste it into
https://app.slack.com/block-kit-builder to see exactly which part Slack objects
to — much faster than guessing.

### My bot has no name or icon

Set them at api.slack.com/apps → your app → Basic Information → Display
Information. Cosmetic, but it makes test messages look intentional.

---

## Phase 4 problems

### Two Slack messages for one event

The deduplication is not working. Check:

1. Does the unique constraint exist in the database? Having it on the model is
   not enough — you need to have run `makemigrations` and `migrate`.
2. Are you using `get_or_create` and checking the `created` boolean, rather than
   a separate `filter().exists()` check? Document 06 explains why the latter has
   a race condition.
3. Is the `google_event_id` actually populated? If it is empty or `None` for both
   rows, the constraint may not be catching them the way you expect.

### The Slack message arrives but the event link does not work

Check that you are using `htmlLink` from Google's creation response rather than
constructing a URL yourself. Google's event IDs are not directly usable in a URL
without encoding.

### The event was created but no Slack message, and no error shown

Check in order:

1. Was a `slack_channel_id` actually included in the request?
2. Is there an `EventNotification` row? If yes, what is its `status` and `error`?
3. Is the `slack` object present in the response, and is the frontend rendering
   it? A missing amber warning in the UI is a frontend bug, not an integration
   one.

That second check is why the table is useful beyond deduplication — it records
what happened even when nothing was displayed.

### A Slack failure returns 500 and the user thinks nothing happened

The `notify_event_created()` function is raising instead of returning a status.
It must not raise on a Slack-side failure, because the calendar event has already
been created and a 500 would make the user retry and create a duplicate.
Document 06 covers the reasoning.

---

## Phase 5 problems

### The event list does not refresh after creating an event

You created the event and updated the server, but the component is still showing
data it fetched earlier. Re-fetch the list after a successful creation.

### A `401` from my own backend after connecting

Your `fetch` calls are not sending the session cookie. Add `credentials:
"include"` in `client.ts`, and make sure Django's CORS configuration has
`CORS_ALLOW_CREDENTIALS = True`.

Note that `CORS_ALLOW_ALL_ORIGINS` cannot be combined with credentialed
requests — browsers reject that combination deliberately. You need an explicit
origin list, which is what we have.

### TypeScript complains that a field might be undefined

That is TypeScript doing its job. The `slack` object can be `null` when no
channel was chosen, and `error` is absent when the status is `"sent"`. Handle the
cases rather than silencing the warning with `!` or `any` — the compiler is
pointing at a real branch you have not written yet.

### The form submits twice when I double-click

Disable the button while the request is in flight. And remember from document 06
that this is a UX improvement, not the correctness fix — the backend constraint
is what actually guarantees one message.

---

## Phase 6 problems

### Tests fail with "Database access not allowed"

Add the `@pytest.mark.django_db` marker to tests that touch the database, or
configure it globally in `pytest.ini`.

### Tests are slow, or fail when I am offline

Some test is calling the real Google or Slack. Find it and mock it with
`responses`. Tests must never depend on the network: they need to be fast enough
to run constantly, and able to simulate failures you cannot trigger on demand.

### Tests pass individually but fail together

Usually shared state leaking between tests — a database row one test created that
another test did not expect. Each test should set up what it needs rather than
relying on what ran before it.

---

## Useful commands

```powershell
# Backend
cd backend
.\venv\Scripts\activate
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py shell            # a Python prompt with Django loaded
pytest -v

# Frontend
cd frontend
npm run dev
npm run build

# Testing endpoints (note curl.exe, not curl, in PowerShell)
curl.exe http://localhost:8000/api/health/
curl.exe http://localhost:8000/api/calendar/events/
curl.exe -X POST http://localhost:8000/api/slack/test-message/ `
  -H "Content-Type: application/json" `
  -d '{"channel_id":"C04IJKLMNOP"}'

# Inspecting the database from the Django shell
python manage.py shell
>>> from google_calendar.models import GoogleCredential
>>> c = GoogleCredential.objects.first()
>>> c.expires_at                  # when does the token expire?
>>> len(c.access_token)           # is anything actually stored?
```

That last pair is worth remembering. "Is there a value, and when does it expire"
answers a large share of token questions in about ten seconds.

---

## Places to revoke access when you want to start clean

Sometimes the quickest way forward is a reset.

**Google:** https://myaccount.google.com/permissions — find your app and remove
access. The next Connect will be a fresh first-time consent, which also means a
new refresh token.

**Slack:** your workspace → Settings & administration → Manage apps → your app →
Remove. Or from api.slack.com/apps → your app → Install App.

**Locally:** delete `backend/db.sqlite3` and run `python manage.py migrate`
again. This throws away all stored tokens and gives you a clean database. Safe to
do at any point in this project — there is nothing in there you cannot
regenerate by clicking Connect again.

---

Back to: [00 — Start Here](00-start-here.md)
