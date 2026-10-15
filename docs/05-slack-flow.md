# 05 — The Slack Flow

Good news first: Slack's OAuth is the same shape as Google's. Send the user to an
authorize URL, get a code back on a callback, swap the code plus your client
secret for a token, store the token. If document 03 and 04 made sense, most of
this will feel familiar.

So this document spends less time on the flow and more time on the three things
that are genuinely different, because those are where people get stuck.

Read this before Phase 3.

---

## The three ways Slack differs from Google

### 1. You install into a workspace, not into a personal account

With Google, you asked a *person* for permission to touch *their* calendar. The
token represents "this app, acting on behalf of this user."

With Slack, you install an **app** into a **workspace**. What you get back is a
**bot token**, and it represents a new identity that now lives in that workspace
— a bot user with a name and an avatar that can post messages as itself.

That is why Slack messages from integrations say things like "Calendar Demo
APP 2:14 PM" rather than appearing to come from you. The bot is its own
participant.

Slack can also issue a **user token** (`xoxp-`) that acts *as you*, the way
Google's does. We are not using one. A bot token is the right choice here for
three reasons: the notification is from the app, not pretending to be a person;
the integration keeps working if you leave the company; and the permissions are
clearer to everyone in the workspace.

You will see both prefixes in Slack's documentation, so it is worth being able to
tell them apart:

```
xoxb-...    bot token     the app's own identity          ← what we use
xoxp-...    user token    acts as a specific human
xapp-...    app-level     for socket mode and events, not relevant here
```

### 2. Bot tokens do not expire

There is no refresh dance. No `expires_at` column, no sixty-second margin, no
`invalid_grant` handling. You store the token and it keeps working until somebody
uninstalls the app or revokes it.

This makes Phase 3 noticeably simpler than Phase 2 was.

Slack does offer **token rotation** as an opt-in feature, where bot tokens expire
after twelve hours and you refresh them much like Google's. We are leaving it
off. If you turn it on later, the pattern you already learned for Google applies
almost unchanged — which is a nice demonstration of why learning the pattern beats
learning the provider.

### 3. Slack returns HTTP 200 when things fail

This is the one that will catch you, so I am putting it in its own section.

---

## The `ok: false` trap

Google returns a `403` status code when you lack permission. Slack returns:

```
HTTP/1.1 200 OK
Content-Type: application/json

{ "ok": false, "error": "missing_scope",
  "needed": "channels:read", "provided": "chat:write" }
```

**Status 200. Body says it failed.**

If you write the obvious thing:

```python
response = requests.post(url, ...)
if response.status_code == 200:
    print("Message sent!")      # wrong — it may well not have been
```

then your app will cheerfully report success for every kind of Slack failure.
This is a real bug that reaches production in real companies.

The rule is simple and absolute: **every Slack API response must be checked for
`ok`.**

```python
data = response.json()
if not data.get("ok"):
    raise SlackError(data.get("error", "unknown_error"))
```

We will write exactly one function that makes Slack calls and performs this
check, and route every Slack request through it. That way the check cannot be
forgotten in one place.

Why does Slack work this way? Largely history — the Web API predates the current
convention of mapping application errors onto HTTP status codes. There is an
upside, though: the error strings are specific and genuinely useful.
`not_in_channel` tells you precisely what is wrong, which is more than a bare
`403` does. Slack does use real status codes for transport-level problems such as
`429` rate limiting.

---

## Part 1: Creating the Slack app

Unlike Google, where you create "credentials" in a cloud console, Slack has you
create an **app** — an actual entity with a name, an icon and a personality.

The steps (document 08 has the click-by-click version):

1. Go to https://api.slack.com/apps and choose **Create New App**, then **From
   scratch**.
2. Give it a name and pick the workspace to develop it in.
3. On the **OAuth & Permissions** page, add the redirect URL and the bot scopes.
4. Copy the **Client ID** and **Client Secret** from **Basic Information** into
   `backend/.env`.

One instruction that matters: there is a big inviting **Install to Workspace**
button on that page. **Do not click it.**

That button performs the installation for you and hands you a ready-made bot
token, which would skip the entire exercise. We are going to install the app
through our own OAuth flow, because building that flow is the point of Phase 3.

---

## Part 2: The scopes we ask for, and why exactly these three

Slack's scopes are more granular than Google's, which is a good thing once you
are used to it. We need three.

### `channels:read`

Lets us call `conversations.list` to fetch the public channels in the workspace,
so the user can pick one from a dropdown.

Why not more? There are sibling scopes — `groups:read` for private channels,
`im:read` for direct messages, `mpim:read` for group DMs. Each one would let our
app see a category of conversation it has no business seeing. A demo that posts
event announcements does not need visibility into anyone's private channels or
DMs, so we do not ask.

### `chat:write`

The minimum needed to call `chat.postMessage` at all. Without it we can read
channel names and do nothing else.

### `chat:write.public`

This lets the bot post to a **public channel it has not been invited to**.

It is worth understanding what happens without it, because the failure is
confusing. With only `chat:write`, the bot can post exclusively to channels it is
a member of. Your channel dropdown would list every public channel, the user
would pick one, and Slack would reject the post with:

```json
{ "ok": false, "error": "not_in_channel" }
```

The only fixes would be to have the user type `/invite @YourApp` in every channel
they want to use, or to call `conversations.join` first. Both are extra friction
for a demo.

One additional scope removes the whole problem. This is a good example of least
privilege being a judgement rather than a reflex: the smallest *possible* set of
scopes is not always the smallest *sensible* one. You weigh what the app genuinely
needs to work against what you are asking users to trust you with.

### Scopes we are explicitly not asking for

Worth naming, so you can see the shape of what we declined:

```
users:read          we never need the member list
channels:history    we never read messages, only write them
files:write         we never upload files
chat:write.customize   lets the bot post under a different name and
                       avatar — unnecessary, and slightly deceptive
```

---

## Part 3: The installation flow

```
   You / Browser              Our Backend                      Slack
        │                          │                              │
  (1)   │  click "Connect Slack"   │                              │
        ├─────────────────────────►│                              │
        │                          │  make a random `state`       │
        │                          │  store it in the session     │
  (2)   │   "go to this Slack URL" │                              │
        │◄─────────────────────────┤                              │
        │                                                          │
  (3)   │  GET slack.com/oauth/v2/authorize?...                    │
        ├─────────────────────────────────────────────────────────►│
        │                                                          │
  (4)   │   "Calendar Demo is requesting permission to access      │
        │    the Acme workspace"                                   │
        │    • View basic information about public channels         │
        │    • Send messages as Calendar Demo                      │
        │               [ Allow ]  [ Cancel ]                      │
        │◄────────────────────────────────────────────────────────►│
        │          you click Allow                                 │
        │                                                          │
  (5)   │  redirect to localhost:8000/api/slack/oauth/callback/    │
        │     ?code=1234567890.98765&state=xyz                     │
        │◄─────────────────────────────────────────────────────────┤
        ├─────────────────────────►│                              │
        │                   (6) check `state` matches              │
        │                   (7) POST slack.com/api/oauth.v2.access │
        │                       code + client_id + CLIENT_SECRET   │
        │                          ├────────────────────────────► │
        │                          │  { ok: true,                 │
        │                          │    access_token: "xoxb-...", │
        │                          │    team: {...}, ... }        │
        │                          │◄──────────────────────────── │
        │                   (8) encrypt token, save it with the    │
        │                       workspace id and granted scopes    │
  (9)   │  redirect to localhost:5173/?slack=connected             │
        │◄─────────────────────────┤                              │
```

### The authorize URL

```
https://slack.com/oauth/v2/authorize
  ?client_id=1234567890.9876543210
  &scope=channels:read,chat:write,chat:write.public
  &redirect_uri=http://localhost:8000/api/slack/oauth/callback/
  &state=T8kP2mNq7vX1wR4sL9bY
```

Differences from Google's URL worth noticing:

- Scopes are separated by **commas**, where Google uses spaces.
- There is no `response_type=code`; Slack's v2 authorize endpoint only does the
  code flow, so there is nothing to choose.
- There is no `access_type=offline` or `prompt`, because there are no refresh
  tokens to request.
- The `scope` parameter means **bot** scopes. If you ever want user scopes, they
  go in a separate `user_scope` parameter. Mixing these up is a common confusion.

The `redirect_uri` must match what you saved on the OAuth & Permissions page,
with the same exactness Google demands. And on that page there is a **Save URLs**
button that is easy to overlook — adding the URL without saving leaves you
debugging a mismatch that looks impossible.

### The token exchange

```
POST https://slack.com/api/oauth.v2.access
Content-Type: application/x-www-form-urlencoded

code=1234567890.98765
&client_id=1234567890.9876543210
&client_secret=YOUR-SLACK-CLIENT-SECRET
&redirect_uri=http://localhost:8000/api/slack/oauth/callback/
```

A successful response:

```json
{
  "ok": true,
  "access_token": "xoxb-YOUR-BOT-TOKEN",
  "token_type": "bot",
  "scope": "channels:read,chat:write,chat:write.public",
  "bot_user_id": "U04ABCDEFGH",
  "app_id": "A04ABCDEFGH",
  "team": { "id": "T04ABCDEFGH", "name": "Acme Inc" },
  "authed_user": { "id": "U04ZYXWVUTS" }
}
```

What we store, and why each piece is worth keeping:

| Field | Why we save it |
|---|---|
| `access_token` | The bot token. Encrypted. This is the credential |
| `team.id` | Identifies the workspace. Essential the moment you support more than one |
| `team.name` | So the UI can say "Connected to Acme Inc" rather than "Connected to T04ABCDEFGH" |
| `bot_user_id` | Lets you recognise your own bot's messages, and is useful for debugging |
| `scope` | A record of what was actually granted, so you can give a precise error if something is missing later |

---

## Part 4: Listing channels

```
GET https://slack.com/api/conversations.list
      ?types=public_channel
      &exclude_archived=true
      &limit=200
Authorization: Bearer xoxb-YOUR-BOT-TOKEN
```

### The parameters

**`types=public_channel`** — only public channels. The other values are
`private_channel`, `mpim` and `im`. Each requires its own scope, and we did not
request those, so asking for them would just produce an error.

**`exclude_archived=true`** — archived channels still exist but nobody is
reading them. Posting into one is the integration equivalent of shouting into an
empty room.

**`limit=200`** — how many per page. The maximum Slack recommends.

### The response

```json
{
  "ok": true,
  "channels": [
    { "id": "C04ABCDEFGH", "name": "general",
      "is_channel": true, "is_archived": false, "num_members": 12 },
    { "id": "C04IJKLMNOP", "name": "demo-notifications",
      "is_channel": true, "is_archived": false, "num_members": 3 }
  ],
  "response_metadata": { "next_cursor": "dXNlcjpVMDYxTkZUVDI=" }
}
```

Note that we send the channel **ID** when posting, not the name. `C04IJKLMNOP`,
not `#demo-notifications`. Names can be changed by anyone with permission; IDs
never change. Our dropdown will show the name and submit the ID — a small habit
that prevents a whole class of "it broke after someone renamed the channel" bug.

### Pagination, and why we will handle it properly

See `next_cursor` in `response_metadata`? If it is a non-empty string, there are
more channels. To get them you call again with `&cursor=dXNlcjpVMDYxTkZUVDI=`.

It is tempting to ignore this. Your workspace probably has fifteen channels, one
page covers it, and the code works.

Then it is deployed to a company with 900 channels, and the channel the user
wanted is on page three, and it simply is not in the dropdown. Nothing errors.
Nothing logs. The feature is quietly broken for exactly the customers who matter
most.

This is the classic "works on my machine" integration failure, and it is caused
by testing against a small dataset. So we will write the loop — about five lines
— and I will point out that noticing pagination in documentation is a habit worth
building. Whenever you see `cursor`, `next_page_token` or `has_more` in an API
response, there is a loop you are supposed to write.

---

## Part 5: Sending a message

```
POST https://slack.com/api/chat.postMessage
Authorization: Bearer xoxb-YOUR-BOT-TOKEN
Content-Type: application/json; charset=utf-8

{
  "channel": "C04IJKLMNOP",
  "text": "New event: Design review — Tue 20 Oct, 3:00-4:00 PM IST",
  "blocks": [
    { "type": "header",
      "text": { "type": "plain_text", "text": "New calendar event" } },
    { "type": "section",
      "text": { "type": "mrkdwn",
                "text": "*Design review*\nWalk through the new onboarding flow" } },
    { "type": "section",
      "fields": [
        { "type": "mrkdwn", "text": "*When*\nTue 20 Oct, 3:00-4:00 PM IST" },
        { "type": "mrkdwn", "text": "*Attendees*\n2 invited" }
      ] },
    { "type": "actions",
      "elements": [
        { "type": "button",
          "text": { "type": "plain_text", "text": "Open in Google Calendar" },
          "url": "https://www.google.com/calendar/event?eid=YTFiMmMzZDQ" }
      ] }
  ]
}
```

### `text` is required even when you use `blocks`

`blocks` are Slack's rich layout system — headers, columns, buttons. `text` is
plain text.

When you supply `blocks`, Slack renders those in the channel and seems to ignore
`text`. So why include it?

Because `text` is the **fallback**, and it is used in:

- mobile and desktop push notifications
- the notification preview in the channel sidebar
- screen readers
- any Slack client that cannot render your block types

Leave it out and users get a push notification that says, essentially, nothing.
Slack will also log a warning. So: always set `text` to a readable one-line
summary of the message, even when `blocks` carries the real content.

### A note on taste

Our message should include the event title, the date and time, and a link to the
event — that is what makes a notification useful. What it should not include is
everything we happen to know. The full attendee email list in a public channel is
a small privacy leak nobody asked for; "2 invited" conveys the same useful
information. Deciding what *not* to put in an automated message is part of the
job.

---

## Slack errors you will actually hit

| `error` string | What happened | What to do about it |
|---|---|---|
| `missing_scope` | A scope you need was not granted at install time. The response includes `needed` and `provided`, which is helpful | **Code cannot fix this.** The app must be reinstalled so the user can consent to the new scope. Surface that instruction clearly |
| `not_in_channel` | Bot is not a member, and `chat:write.public` is missing | Add the scope and reinstall, or call `conversations.join` first |
| `channel_not_found` | The channel ID is wrong, or it is a channel this token cannot see | Refresh the channel list; the channel may have been archived or deleted |
| `invalid_auth` | The token is not valid | Treat as disconnected. Do not retry |
| `token_revoked` | Someone uninstalled the app or revoked the token | Treat as disconnected, prompt a reconnect |
| `account_inactive` | The bot user was deactivated | Treat as disconnected |
| `is_archived` | The channel is archived | Tell the user to choose another channel |
| `msg_too_long` | Message text exceeded the limit | Truncate before sending |
| `ratelimited` or HTTP **429** | Too many requests | Wait, then retry — details below |
| `invalid_blocks` | Your block JSON is malformed | A bug in your message builder. Test with Block Kit Builder |

A pattern to notice: these errors fall into three groups, and the right response
differs for each.

1. **The user must act** — `missing_scope`, `not_in_channel`, `is_archived`. No
   amount of retrying helps. Explain clearly what they need to do.
2. **The connection is dead** — `invalid_auth`, `token_revoked`,
   `account_inactive`. Mark it disconnected and stop.
3. **Try again shortly** — `ratelimited`, and transient network failures. These
   are the *only* ones worth retrying.

Retrying an error from group 1 or 2 is pure waste. Part of writing a good
integration is classifying errors correctly, and most error handling that
annoys users does so because it retries things that cannot succeed.

---

## Rate limits

Slack puts its methods into tiers. The two we use:

**`conversations.list`** is Tier 3 — roughly 50 requests per minute. We call it
when the user loads the page, so we are nowhere near this. Still, caching the
channel list for a minute rather than fetching it on every keystroke is the kind
of courtesy that keeps you out of trouble.

**`chat.postMessage`** has its own special limit: about **one message per second
per channel**, with short bursts tolerated. Plenty for our use, where one event
creates one message.

When you exceed a limit, Slack responds:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30

{ "ok": false, "error": "ratelimited" }
```

**Honour `Retry-After` exactly.** Not half of it, not a guess, not immediately.
That header is the server telling you precisely when it will accept you again,
and ignoring it is how an integration goes from "temporarily throttled" to
"blocked."

We will implement a single bounded retry: wait for `Retry-After`, try once more,
and if that also fails, report the failure honestly rather than looping. Infinite
retry loops are how a small hiccup turns into an outage of your own making.

---

## Part 6: The endpoints we will build

```
GET  /api/slack/oauth/start/
     Makes the state value, builds the authorize URL, redirects to Slack.

GET  /api/slack/oauth/callback/
     Validates state, exchanges the code via oauth.v2.access, stores the
     encrypted bot token plus workspace details, redirects to the frontend.

GET  /api/slack/channels/
     Returns the public channels as a simple list of {id, name} for the
     dropdown, following pagination.

POST /api/slack/test-message/
     A temporary endpoint that posts a fixed message to a channel you choose.

     This exists so that Slack can be proven to work completely on its own,
     before it is wired to anything else. When Phase 4 connects the two
     integrations, if a message fails to arrive you will already know with
     certainty that the Slack half works — which means the bug is in the new
     code. Being able to narrow down where a bug cannot be is most of
     debugging. We delete this endpoint in Phase 6.
```

---

## Official documentation

- Installing with OAuth: https://api.slack.com/authentication/oauth-v2
- `oauth.v2.access`: https://api.slack.com/methods/oauth.v2.access
- `conversations.list`: https://api.slack.com/methods/conversations.list
- `chat.postMessage`: https://api.slack.com/methods/chat.postMessage
- Scopes reference: https://api.slack.com/scopes
- Rate limits: https://api.slack.com/docs/rate-limits
- Block Kit Builder, for designing messages visually:
  https://app.slack.com/block-kit-builder

---

Next: [06 — Connecting Both Integrations](06-connecting-both.md)
