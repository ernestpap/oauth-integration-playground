# 09 — Implementation Plan

Six phases. Each one ends with a checklist, and I stop there and wait until you
confirm it works on your machine before we start the next one.

The time estimates assume you are reading and understanding rather than
copy-pasting, and that some things go wrong. They usually do, and the debugging
is part of the learning rather than an interruption to it.

---

## Why we work in phases

Integration bugs compound in a particular way that makes the phase discipline
worth following.

Suppose your token storage has a subtle fault in Phase 2 — the encryption works,
but you accidentally store the refresh token truncated. Everything appears fine,
because the access token is valid for an hour and you are testing inside that
hour.

Then in Phase 4 your Slack notification does not arrive. You start looking at the
Slack code. You check the scopes, the channel ID, the message format. You spend
an hour in entirely the wrong file, because the actual error is a Google token
refresh failing and aborting the request before Slack was ever reached.

The phase checkpoints exist to shrink the number of possible explanations for any
bug. If Phase 3 is confirmed working, and something breaks in Phase 4, then the
fault is almost certainly in the few lines Phase 4 added. That narrowing is worth
more than the time it costs.

---

## Phase 1 — Project setup

**About 45 minutes.**

### What we are building and why

Nothing interesting, deliberately. The goal of this phase is to end up with two
servers running, talking to each other, with configuration loaded properly and
git set up so that secrets cannot leak.

It is tempting to skip ahead to OAuth. Resist it. If something is misconfigured
here, you will discover it in Phase 2 while also learning OAuth, and you will not
know which of the two is at fault. Get the boring foundation verified first.

### Steps

1. `git init`, then write `.gitignore` **before** any `.env` file exists.
2. Create the Python virtual environment and install the backend packages.
3. Create the Django project (`config/`) and the three apps.
4. Write `settings.py` to read from `.env`, including CORS configuration for
   `localhost:5173`.
5. Create `.env.example`, then `.env`, generating the two random keys.
6. Build `GET /api/health/`, which returns `{"status": "ok"}`.
7. Scaffold the React app with Vite and TypeScript.
8. Write `src/api/client.ts` and have `App.tsx` display the health endpoint's
   response.

### What you will understand by the end

- What Django's project/app distinction actually means
- Why `.env` exists and how `python-dotenv` loads it
- What CORS is, why it blocks you, and what we configured to allow
- Why two servers during development, and what changes in production
- What git is and is not protecting you from

### Checklist

- [ ] `git status` shows `.env` is **not** listed as a file to be committed
- [ ] `python manage.py runserver` starts with no errors
- [ ] `curl.exe http://localhost:8000/api/health/` returns `{"status": "ok"}`
- [ ] `npm run dev` starts the frontend
- [ ] Opening `http://localhost:5173` shows the status fetched live from Django
- [ ] The browser console shows no CORS errors
- [ ] You can explain what each file in `config/` is for

---

## Phase 2 — Google Calendar

**About two hours. The largest phase.**

### What we are building and why

The complete Google integration: the OAuth flow, encrypted token storage, token
refresh, and the two Calendar API endpoints.

This is the phase with the most new ideas in it, so we will go slowly and test
after each piece rather than writing it all and hoping.

### Steps

**2a.** Configure Google Cloud — document 08 has the clicks. I will guide, you
click.

**2b.** `integrations/crypto.py` — `encrypt()` and `decrypt()` using Fernet. Then
the `GoogleCredential` model and its migration. We will store and read back a
test value before building anything on top of it.

**2c.** `integrations/oauth_state.py`, then `GET /api/google/oauth/start/`. At
this point you can click through to Google's consent screen and see it. The
callback will not exist yet, so the redirect back will 404 — that is expected, and
seeing it 404 confirms the first half works.

**2d.** `GET /api/google/oauth/callback/` — validate `state`, exchange the code,
store the encrypted tokens. Now the full round trip works. We will look in the
database and confirm the stored values are unreadable ciphertext.

**2e.** The refresh logic in `oauth.py`. We will test it by manually editing the
stored `expires_at` to a time in the past and watching a refresh happen in the
server log.

**2f.** `client.py` plus `GET /api/calendar/events/`. Test with `curl`. You should
see your real calendar in the terminal.

**2g.** `serializers.py` plus `POST /api/calendar/events/`. Test with `curl`, then
look at Google Calendar in your browser and see the event you just created from a
terminal.

### What you will understand by the end

- The authorization code flow, concretely, having built it
- Why the code is exchanged server-side and what the client secret proves
- The difference between access and refresh tokens, in working code
- Encryption at rest, and its limits
- The `state` parameter and the attack it prevents
- Scopes, and why `calendar.events` rather than `calendar`
- How to read Google's API reference and turn it into a request

### Checklist

- [ ] Clicking Connect Google reaches Google's consent screen
- [ ] After allowing, you land back on the frontend showing "connected"
- [ ] Opening the database shows the tokens as unreadable ciphertext, not plain text
- [ ] `curl.exe http://localhost:8000/api/calendar/events/` returns your real events
- [ ] A `POST` creates an event that appears in Google Calendar
- [ ] Attendees receive an email invitation
- [ ] Forcing `expires_at` into the past causes a visible refresh in the logs
- [ ] Tampering with the `state` value gets the request rejected with `400`
- [ ] No token appears anywhere in your terminal output

That second-to-last item is worth doing deliberately. Start the flow, then edit
the `state` in the callback URL before loading it. Seeing your own security check
reject the request is more convincing than trusting that it would.

---

## Phase 3 — Slack, on its own

**About 90 minutes.**

### What we are building and why

The whole Slack integration, with no connection to the Google side at all.

Building it in isolation is a deliberate choice. When Phase 4 wires the two
together, if a notification fails to arrive, you will already know with certainty
that the Slack half works — so the fault must be in the new code. Being able to
rule things out is most of debugging.

### Steps

**3a.** Configure the Slack app — document 08 has the clicks. Remember not to
press Install to Workspace.

**3b.** The `SlackInstallation` model, reusing the same `crypto.py` from Phase 2.

**3c.** The install flow: `oauth/start/` and `oauth/callback/`, reusing the same
`oauth_state.py`. This should feel noticeably quicker than Phase 2 did — that is
the pattern paying off.

**3d.** `client.py` with the single `ok: false` check that every Slack call goes
through, then `GET /api/slack/channels/` including cursor pagination.

**3e.** `POST /api/slack/test-message/` — a temporary endpoint, deleted in Phase 6,
that proves Slack works end to end.

**3f.** Error mapping: turning `missing_scope`, `not_in_channel`,
`channel_not_found` and friends into messages a user could act on.

### What you will understand by the end

- How a Slack app differs from Google's OAuth client
- Bot tokens versus user tokens, and why we chose bot
- Why `ok: false` arrives with HTTP 200, and what that means for your code
- Cursor pagination, and the bug that comes from ignoring it
- How to classify errors into "user must act", "connection dead" and "retry"
- Rate limits and `Retry-After`

### Checklist

- [ ] Clicking Connect Slack reaches Slack's install page, listing your three scopes
- [ ] After allowing, you land back on the frontend showing the workspace name
- [ ] The bot token in the database is ciphertext
- [ ] `curl.exe http://localhost:8000/api/slack/channels/` lists your channels
- [ ] A test message arrives in `#demo-notifications`
- [ ] The message shows your bot's name and icon
- [ ] Sending to a deliberately wrong channel ID returns a clear error, not a crash
- [ ] You have read one real `ok: false` response and know which branch handled it

---

## Phase 4 — Connecting the two

**About one hour.**

### What we are building and why

The single seam between the integrations, and the three-outcome response.

This is the smallest phase by line count and the most interesting by ideas.
Document 06 is the reading for it, and I would suggest re-reading it just before
we start.

### Steps

**4a.** The `EventNotification` model, with `UNIQUE (google_event_id,
channel_id)`.

**4b.** `notifications.py` with `notify_event_created()`.

**4c.** Wire it into the event creation view, in the order from document 06:
validate, create in Google, claim the notification, post to Slack, respond.

**4d.** Build the three-outcome response shape.

**4e.** Break things on purpose and watch what happens:
   - a valid Google connection with a deliberately corrupted Slack token
   - the same request sent twice in quick succession
   - a channel ID that does not exist

### What you will understand by the end

- Why there is no transaction across two companies
- Why "undo the event" is the wrong instinct
- Partial success as a first-class outcome
- Idempotency, and why a unique constraint beats an `if` statement
- What a race condition is and where it hides
- Why keeping the coupling to one function made this phase small

### Checklist

- [ ] Creating an event posts a message to the chosen Slack channel
- [ ] The Slack message contains the title, the date and time, and a working link
      to the event
- [ ] Clicking the link opens the right event in Google Calendar
- [ ] Sending the same request twice creates **one** Slack message
- [ ] With a broken Slack token, the event is still created and the response says
      precisely why Slack failed
- [ ] With Google broken, no Slack message is sent at all
- [ ] The `EventNotification` table shows a row per attempt with the right status

---

## Phase 5 — Frontend

**About two hours.**

### What we are building and why

The user interface. Everything already works through `curl`; this phase makes it
pleasant.

Doing the frontend last is deliberate. If you build the UI first, then every
backend bug arrives wrapped in a layer of React, and you will not know which side
is at fault. With the API already proven, anything that breaks here is a frontend
problem.

### Steps

**5a.** `types.ts` — TypeScript types mirroring the API, including the
three-state `slack` object.

**5b.** `IntegrationStatus.tsx` — connection status and the two Connect buttons.

**5c.** `UpcomingEvents.tsx` — the event list, handling both timed and all-day
events.

**5d.** `CreateEventForm.tsx` — the form, with client-side validation for instant
feedback.

**5e.** `ChannelPicker.tsx` — the dropdown, showing names and submitting IDs.

**5f.** `Alert.tsx` — and wiring up all three outcomes, with the amber partial
success case rendered properly.

**5g.** Loading states, and disabling the submit button while a request is in
flight.

### What you will understand by the end

- Which validation belongs in the frontend and which in the backend, and why the
  answer is both for different reasons
- Why a disabled button is UX and not a correctness guarantee
- How to render three outcomes rather than two
- Why components depend on our API's shape rather than Google's
- What TypeScript catches here that plain JavaScript would not

### Checklist

- [ ] Both Connect buttons work from the UI
- [ ] Status correctly shows connected and not-connected states
- [ ] Upcoming events display, including any all-day events
- [ ] The form rejects an end time before the start time, immediately
- [ ] The channel dropdown is populated from Slack
- [ ] A successful creation shows a green message and the new event appears in the list
- [ ] A Slack failure shows an amber warning, not a red error and not a green success
- [ ] The submit button disables while the request is in flight
- [ ] Nothing sensitive appears in the browser's network tab or console

---

## Phase 6 — Testing, review and documentation

**About 90 minutes.**

### What we are building and why

Automated tests for the integration logic, the README, and an honest review of
every shortcut we took.

The tests matter in a specific way. The paths worth testing here are the failure
paths — expired tokens, missing scopes, revoked access — and those are exactly
the ones you cannot reproduce by hand on demand. You cannot ask Google to return
a 403 at a convenient moment. So you fake its response, and suddenly the hardest
paths become the easiest to verify.

### Steps

**6a.** Configure pytest with Django.

**6b.** Write the tests that matter:

```
test_state_mismatch_is_rejected
test_refresh_happens_when_token_is_near_expiry
test_refresh_keeps_existing_refresh_token_when_none_returned
test_invalid_grant_marks_integration_disconnected
test_slack_ok_false_raises_a_specific_error
test_missing_scope_produces_a_reinstall_instruction
test_duplicate_notification_is_not_sent_twice
test_slack_failure_still_returns_the_created_event
test_google_failure_prevents_any_slack_message
test_end_before_start_is_rejected
```

Every one of those corresponds to something from documents 03 to 06. The test
suite is a checklist of the things you learned.

**6c.** Mock all third-party HTTP with `responses`. No test ever calls the real
Google or Slack — tests must be fast, offline and repeatable.

**6d.** Manual testing of things that are easier to do by hand than to automate:
revoke access in your Google account settings and watch the reconnect path;
uninstall the Slack app and watch `token_revoked` handled.

**6e.** Write the README: setup, configuration, running, testing.

**6f.** Write `docs/architecture.md` with the final diagram.

**6g.** Switch to PostgreSQL, to see that it is a configuration change rather
than a code change.

**6h.** Delete the temporary `test-message` endpoint.

**6i.** The production readiness review — document 10, walked through properly,
naming every shortcut and its replacement.

### What you will understand by the end

- How to test integration code without touching the real services
- Why the failure paths are the ones worth testing
- What a mock is and where it stops being useful
- How to debug the errors you have personally hit
- Which of our shortcuts are fine for a demo and which would be negligent in
  production

### Checklist

- [ ] `pytest` runs green
- [ ] Tests pass with your network disconnected
- [ ] The whole suite finishes in a couple of seconds
- [ ] Revoking Google access produces a clear "reconnect required" message
- [ ] Uninstalling the Slack app produces a clear reconnect message
- [ ] `README.md` is complete enough for a stranger to run the project
- [ ] `.env.example` lists every variable with no real values
- [ ] The project runs against PostgreSQL
- [ ] You can name three shortcuts we took and what each would become in production

---

## The shape of the whole thing

```
Phase 1   setup              ████                        45 min
Phase 2   Google             ████████████████           2 hr
Phase 3   Slack              ████████████               90 min
Phase 4   connect them       ████████                   1 hr
Phase 5   frontend           ████████████████           2 hr
Phase 6   tests and docs     ████████████               90 min
                             ────────────────────────────────────
                                                   about 8-9 hours
```

Spread that over however many sessions suit you. The phase boundaries are
natural stopping points, and each one leaves the project in a working state.

One thing to notice in that bar chart: Phase 2 and Phase 5 are the long ones, and
Phase 4 — the one that actually delivers the feature the whole project is named
after — is short. That is not an accident. It is the dividend from keeping the two
integrations independent while building them.

---

Next: [10 — Security Notes](10-security-notes.md)
