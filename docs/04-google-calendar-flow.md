# 04 — The Google Calendar Flow

Document 03 explained OAuth in general. This one is the specific, practical
version for Google: the exact URLs, the exact parameters, what comes back, and
the mistakes that will cost you an afternoon if nobody warns you.

Read this before Phase 2.

---

## Part 1: Sending the user to Google

When you click **Connect Google**, our backend builds a URL and redirects your
browser to it. The URL looks like this, broken across lines for readability:

```
https://accounts.google.com/o/oauth2/v2/auth
  ?client_id=1234567890-abcdef.apps.googleusercontent.com
  &redirect_uri=http://localhost:8000/api/google/oauth/callback/
  &response_type=code
  &scope=https://www.googleapis.com/auth/calendar.events
  &access_type=offline
  &prompt=consent
  &state=T8kP2mNq7vX1wR4sL9bY
  &include_granted_scopes=true
```

Every one of those parameters is doing a job. Here is each one.

### `client_id`

Our app's public identifier, issued by Google when we create the OAuth client in
Phase 2's setup. It is fine for this to be visible in a URL, in your git history,
or in a screenshot. It is a name, not a password.

### `redirect_uri`

Where Google should send the user after they decide. This must **exactly** match
one of the redirect URIs you registered in the Google Cloud Console. Not
"basically match" — exactly.

These are all different values as far as Google is concerned:

```
http://localhost:8000/api/google/oauth/callback/
http://localhost:8000/api/google/oauth/callback      ← no trailing slash
https://localhost:8000/api/google/oauth/callback/    ← https
http://127.0.0.1:8000/api/google/oauth/callback/     ← different host
http://localhost:8000/api/Google/oauth/callback/     ← capital G
```

Getting this wrong produces `Error 400: redirect_uri_mismatch`, and it is the
single most common thing to go wrong in this whole project. We will pick one
spelling, put it in `.env`, and use that same variable everywhere so there is
only one copy to be wrong.

Why is Google so strict? Because this parameter is a security control. If Google
let us send users to any address we liked, an attacker who knew our client ID
could start a flow that redirects authorization codes to their own server. The
pre-registered whitelist is what prevents that.

### `response_type=code`

"Please give me an authorization code, not a token." This chooses the
authorization code flow, the one safe for apps with a backend. Document 03
explains why the code exists at all; the short version is that the code travels
through the browser and is useless without our client secret.

### `scope`

The permissions we want. We ask for exactly one:

```
https://www.googleapis.com/auth/calendar.events
```

This grants reading *and* writing of calendar events, which covers both things
our app does. We do not ask for `.../auth/calendar`, which would additionally
allow creating and deleting entire calendars and changing sharing settings. We do
not need those, so we do not ask.

If you needed several scopes you would separate them with spaces (which become
`%20` or `+` once URL-encoded).

### `access_type=offline`

This one is easy to miss and important. It means: "I need to be able to act on
this user's behalf later, when they are not sitting in front of the browser."

Translated: **send me a refresh token.**

Leave it out and you get an access token that works for about an hour, with no
way to renew it. Your app works beautifully during development and mysteriously
stops after lunch. Then you re-click Connect and it works again, which makes the
bug look intermittent rather than structural.

### `prompt=consent`

This forces Google to show the consent screen every single time, even if the user
has already approved us.

Why would we want to annoy the user like that? Because of a specific Google
behaviour: **Google issues a refresh token only the first time a user consents.**
Authorize a second time without `prompt=consent` and the response contains an
access token but no refresh token.

That is fine if you stored the first one. It is a disaster if you wrote code like
"save whatever came back," because you will overwrite your good refresh token
with `None`.

During development you will connect and reconnect dozens of times, so
`prompt=consent` makes the flow predictable: you always get both tokens, every
time. In a polished production app you would usually drop it and instead write
your storage code carefully, so that a missing refresh token in the response
leaves the stored one alone. We will write it that way regardless — belt and
braces.

### `state`

The random anti-CSRF value from document 03. We generate it, store it in the
Django session, send it to Google, and compare it when the user comes back.

### `include_granted_scopes=true`

Tells Google to give us a token covering everything the user has previously
granted us, not just what we asked for this time. Useful when an app requests
more permissions over time ("incremental authorization"). Harmless here; worth
knowing it exists.

---

## Part 2: What the user sees

Your browser loads a page on `accounts.google.com`. It is Google's page, not
ours. If you are signed out, you sign in there. Your password goes to Google.

Then the consent screen appears. It shows:

- our app's name, which we set on the OAuth consent screen configuration
- what we are asking for, in Google's own wording: *"View and edit events on all
  your calendars"*
- Allow and Deny buttons

Two things you will meet here during Phase 2:

**An "unverified app" warning.** Because our OAuth consent screen is in Testing
mode and our app has not been through Google's verification review, Google shows
a scary interstitial: "Google hasn't verified this app." You click **Advanced**,
then **Go to (app name) (unsafe)**. This is expected and correct for a
development app. Production apps that request sensitive scopes go through a
verification process to remove it.

**"Access blocked: app is in testing mode."** This means your Google account is
not in the **Test users** list in the Cloud Console. Add your own email there and
retry. Document 08 covers this step.

---

## Part 3: The callback

You click Allow. Google redirects your browser to:

```
http://localhost:8000/api/google/oauth/callback/
  ?code=4%2FYOUR-ONE-TIME-CODE
  &scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar.events
  &state=T8kP2mNq7vX1wR4sL9bY
```

Our callback endpoint does four things, in this order.

### Step 1: handle a denial

If the user clicked Deny, there is no `code` — there is `?error=access_denied`
instead. Handle this first and gracefully. The user has not done anything wrong;
they changed their mind. Redirect them back to the app with a neutral message,
not an error page.

### Step 2: validate `state`

Compare the `state` in the query string with the one stored in the session. If it
is missing, or does not match, stop immediately and return `400`. Do not exchange
the code. Do not log the code. Just stop.

Then delete the stored value, so the same callback cannot be replayed.

### Step 3: exchange the code for tokens

This is the server-to-server request. Google never sees our client secret in a
browser; it only arrives here, in the body of a POST made by our Python code.

```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

code=4/YOUR-ONE-TIME-CODE
&client_id=1234567890-abcdef.apps.googleusercontent.com
&client_secret=GOCSPX-YOUR-CLIENT-SECRET
&redirect_uri=http://localhost:8000/api/google/oauth/callback/
&grant_type=authorization_code
```

Note that `redirect_uri` appears again. Google checks it matches the one used in
the first request. Another place the exact-match rule bites.

A successful response:

```json
{
  "access_token": "ya29.YOUR-ACCESS-TOKEN",
  "expires_in": 3599,
  "refresh_token": "1//YOUR-REFRESH-TOKEN",
  "scope": "https://www.googleapis.com/auth/calendar.events",
  "token_type": "Bearer"
}
```

`expires_in` is **seconds from now**, not a timestamp. We convert it immediately:

```
expires_at = now() + 3599 seconds
```

Storing an absolute expiry time rather than a duration is important. A duration is
only meaningful at the instant you received it; by the time you read it out of the
database it means nothing.

### Step 4: store the tokens

We encrypt both tokens, then save them along with `expires_at` and the granted
scopes.

Storing the granted scopes is worth doing even though we know what we asked for.
Users can sometimes grant a subset of what was requested, and having a record
lets us produce a clear error later ("this app was not granted permission to
write events, please reconnect") instead of a confusing `403` from Google.

Then we redirect the browser back to the frontend, which shows "connected."

---

## Part 4: Keeping the token alive

An access token lasts about an hour. Our app needs to work after that hour
without bothering the user, which is what the refresh token is for.

The logic, which we will put in one function and call before every Calendar API
request:

```
def get_valid_access_token():

    credential = load from database
    decrypt the stored tokens

    if credential.expires_at - now() < 60 seconds:

        POST https://oauth2.googleapis.com/token
            grant_type=refresh_token
            refresh_token=<the decrypted refresh token>
            client_id=...
            client_secret=...

        if the response is an error:
            mark the integration disconnected
            raise an error the view turns into a clear message

        save the new access_token
        save the new expires_at = now() + expires_in
        do NOT overwrite the refresh token unless a new one was sent

    return credential.access_token
```

The refresh response looks like this — note what is missing:

```json
{
  "access_token": "ya29.YOUR-NEW-ACCESS-TOKEN",
  "expires_in": 3599,
  "scope": "https://www.googleapis.com/auth/calendar.events",
  "token_type": "Bearer"
}
```

No `refresh_token`. That is normal and expected. Keep using the one you already
have.

### When refresh fails

```json
{
  "error": "invalid_grant",
  "error_description": "Token has been expired or revoked."
}
```

Possible reasons, in rough order of how often you will see them during this
project:

1. **Your consent screen is in Testing mode**, where Google expires refresh
   tokens after **seven days**. You will hit this. It is not your bug.
2. The user revoked access at
   https://myaccount.google.com/permissions
3. The refresh token was unused for six months.
4. The user changed their Google password, in some cases.
5. You accidentally overwrote the stored refresh token with `None` — the bug
   described above.

In every case, the only correct behaviour is: mark the integration as
disconnected, tell the user to reconnect, and stop. No retry loop. A retry cannot
succeed, and hammering the endpoint is how you get rate limited on top of being
broken.

We will deliberately trigger this in Phase 6 by revoking access from your Google
account settings, so you can watch your own error handling work. Breaking things
on purpose is the only way to know your error paths are real.

---

## Part 5: Reading upcoming events

Now the easy part. With a valid access token, calling the Calendar API is an
ordinary HTTP request.

```
GET https://www.googleapis.com/calendar/v3/calendars/primary/events
      ?timeMin=2026-10-14T10:30:00Z
      &maxResults=10
      &singleEvents=true
      &orderBy=startTime
Authorization: Bearer ya29.YOUR-ACCESS-TOKEN
```

### The URL

`primary` is a convenient alias meaning "this user's main calendar." You could
put a specific calendar ID there instead, which is usually an email address.

### The parameters

**`timeMin`** — only return events starting at or after this time. This is what
makes the list "upcoming" rather than "all events since 2019." The format is
RFC 3339, which is the one that looks like `2026-10-14T10:30:00Z`. The `Z` means
UTC.

**`maxResults=10`** — keep the response small. The API would otherwise return up
to 250 at a time.

**`singleEvents=true`** — this one is genuinely important. Without it, a weekly
standup comes back as a *single* event carrying a recurrence rule, and you would
have to interpret that rule yourself to work out when the next occurrence is.
With it, Google expands recurring events into individual dated occurrences, which
is what you want to display.

**`orderBy=startTime`** — sort chronologically. Google only permits this when
`singleEvents=true`, which makes sense: you cannot meaningfully sort an unexpanded
recurrence rule by start time.

### The response

Trimmed to the fields we care about:

```json
{
  "kind": "calendar#events",
  "items": [
    {
      "id": "7qg3k2m1p9d8fh4jsl0a5b6c7d",
      "status": "confirmed",
      "htmlLink": "https://www.google.com/calendar/event?eid=N3FnM2sybTFw",
      "summary": "Daily standup",
      "description": "Quick sync on yesterday and today",
      "start": { "dateTime": "2026-10-15T09:00:00+05:30",
                 "timeZone": "Asia/Kolkata" },
      "end":   { "dateTime": "2026-10-15T09:15:00+05:30",
                 "timeZone": "Asia/Kolkata" },
      "attendees": [
        { "email": "you@example.com", "responseStatus": "accepted",
          "organizer": true, "self": true },
        { "email": "teammate@example.com", "responseStatus": "needsAction" }
      ]
    }
  ],
  "nextPageToken": "CigKGjRxZzNrMm0xcDlkOGZo..."
}
```

Four things worth pointing out.

**`summary` is the title.** Google's naming, not ours. The field you would
naturally call `title` is called `summary` throughout the Calendar API.

**`htmlLink`** is a direct link to the event in Google Calendar's web interface.
Remember this one — we put it in the Slack message in Phase 4, so people can
click straight through from Slack to the event.

**All-day events have no `dateTime`.** They have `start.date` instead, as a plain
`"2026-10-20"` with no time. If your display code assumes `dateTime` always
exists, the first all-day event in someone's calendar will crash your page. We
will handle both shapes.

**`nextPageToken`** means there are more results. We ignore it deliberately
because we only want the next ten, but it is the same cursor-pagination idea you
will meet again in Slack's channel list.

---

## Part 6: Creating an event

```
POST https://www.googleapis.com/calendar/v3/calendars/primary/events
      ?sendUpdates=all
Authorization: Bearer ya29.YOUR-ACCESS-TOKEN
Content-Type: application/json

{
  "summary": "Design review",
  "description": "Walk through the new onboarding flow",
  "start": { "dateTime": "2026-10-20T15:00:00+05:30",
             "timeZone": "Asia/Kolkata" },
  "end":   { "dateTime": "2026-10-20T16:00:00+05:30",
             "timeZone": "Asia/Kolkata" },
  "attendees": [
    { "email": "teammate@example.com" },
    { "email": "manager@example.com" }
  ]
}
```

### `sendUpdates=all`

This controls whether Google emails the attendees. The options are `all`,
`externalOnly` and `none`.

The default is `none`, which produces a confusing outcome: the event is created,
the attendees are listed on it, and not one of them has any idea. You then spend
half an hour wondering why invitations are not arriving when in fact you never
asked for them to be sent.

We pass `all` explicitly so the behaviour is visible in the code.

### Why `timeZone` as well as an offset

The `dateTime` value already contains an offset (`+05:30`), so strictly the
`timeZone` field is redundant for a one-off event. It matters for recurring
events, because "9am every Monday" has to survive daylight saving changes, and
only a named zone like `Asia/Kolkata` can express that. Including it is good
practice and costs nothing.

### The response

You get back the full created event, including fields Google assigned:

```json
{
  "id": "a1b2c3d4e5f6g7h8i9j0k1l2m3",
  "status": "confirmed",
  "htmlLink": "https://www.google.com/calendar/event?eid=YTFiMmMzZDQ",
  "created": "2026-10-14T10:32:11.000Z",
  "summary": "Design review",
  "start": { "dateTime": "2026-10-20T15:00:00+05:30" },
  "end":   { "dateTime": "2026-10-20T16:00:00+05:30" },
  "attendees": [ ... ],
  "organizer": { "email": "you@example.com", "self": true }
}
```

**That `id` matters a great deal.** It is Google's permanent identifier for this
event, and in Phase 4 we use it as the key that stops us sending duplicate Slack
notifications. Hold onto it.

---

## Errors you will meet from Google's APIs

Unlike Slack, Google uses real HTTP status codes, so `response.status_code` is
meaningful.

| Status | Google's error | What it really means | What to do |
|---|---|---|---|
| **401** | `invalid_credentials` | Access token expired or malformed | Refresh once, then retry the call. If it fails again, treat as disconnected |
| **403** | `insufficientPermissions` | Token is valid but the scope does not cover this action | Cannot be fixed by retrying. User must reconnect and grant the scope |
| **403** | `accessNotConfigured` | The Calendar API is not enabled in your Cloud project | Enable it in the Console. A setup mistake, not a runtime one |
| **403** | `rateLimitExceeded` / `quotaExceeded` | Too many requests | Back off and retry with increasing delays |
| **400** | `badRequest` / `timeRangeEmpty` | Your request body or parameters are wrong — most often the end time is before the start time, or a date is not valid RFC 3339 | Fix the request. Catch this in your own validation first |
| **404** | `notFound` | No such calendar or event | Check the ID |
| **409** | `duplicate` | An event with that ID already exists | Only relevant if you set IDs yourself |

A Google error body looks like this:

```json
{
  "error": {
    "code": 403,
    "message": "Request had insufficient authentication scopes.",
    "errors": [ { "domain": "global", "reason": "insufficientPermissions" } ],
    "status": "PERMISSION_DENIED"
  }
}
```

The `reason` field is the one to branch on in code. The `message` is the one to
show a developer in a log. Neither is suitable to show a user directly — part of
our backend's job is translating these into something a person can act on.

---

## Part 7: The four endpoints we will build

For reference, here is what Phase 2 produces. Each of these is on **our**
backend, called by **our** frontend.

```
GET  /api/health/
     Returns {"status": "ok"}. No auth, no integration. Built in Phase 1 so
     you have something to test before anything complicated exists.

GET  /api/google/oauth/start/
     Creates the state value, builds the consent URL, redirects the browser
     to Google.

GET  /api/google/oauth/callback/
     Where Google sends the user back. Validates state, exchanges the code,
     stores the encrypted tokens, redirects to the frontend.

GET  /api/calendar/events/
     Returns the next ten upcoming events as JSON, in a shape convenient for
     our React components — not Google's raw response.

POST /api/calendar/events/
     Validates the submitted event, refreshes the token if needed, creates the
     event in Google Calendar, and returns what was created. In Phase 4 this is
     where the Slack notification gets added.
```

Notice that we reshape Google's response rather than passing it straight through.
That is deliberate. Our frontend should depend on *our* API contract, not on
Google's. If Google renames a field, we change one translation function instead
of hunting through React components.

---

## Official documentation

- OAuth 2.0 for web server apps:
  https://developers.google.com/identity/protocols/oauth2/web-server
- `events.list` reference:
  https://developers.google.com/calendar/api/v3/reference/events/list
- `events.insert` reference:
  https://developers.google.com/calendar/api/v3/reference/events/insert
- Calendar API errors:
  https://developers.google.com/calendar/api/guides/errors
- OAuth scopes for Calendar:
  https://developers.google.com/calendar/api/auth

---

Next: [05 — The Slack Flow](05-slack-flow.md)
