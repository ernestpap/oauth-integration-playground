# 02 — Architecture

## The four parts of the system

Before any diagrams, here are the four pieces in words.

**1. The browser.** This runs our React app. It draws buttons, forms and lists.
It knows how to call our own backend and nothing else. It holds no secrets.

**2. Our backend.** A Django server running on your machine at port 8000. This is
the brain. It holds the secrets, talks to Google and Slack, stores tokens in the
database, and decides what is allowed.

**3. The database.** SQLite to begin with, which is just a file on disk. It
remembers the tokens we were given, so you do not have to click "Connect Google"
every time you reload the page.

**4. Google and Slack.** Other companies' servers, out on the internet. We do not
control them. They can be slow, they can return errors, and they can change their
minds about whether we are allowed in.

---

## The diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  YOUR BROWSER                                                            │
│                                                                          │
│   React + TypeScript, served by Vite on http://localhost:5173            │
│                                                                          │
│   • Integration status page   • Upcoming events list                     │
│   • Create event form         • Slack channel dropdown                   │
│                                                                          │
│   Holds NO secrets. The only URL it knows is our own backend.            │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │
                             │  fetch() calls carrying the session cookie,
                             │  sending and receiving JSON
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  OUR BACKEND — Django + Django REST Framework, http://localhost:8000     │
│                                                                          │
│  This line is the trust boundary. Secrets exist below it, never above.   │
│                                                                          │
│   ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐   │
│   │ google_calendar  │   │   slack_app      │   │   integrations     │   │
│   │                  │   │                  │   │                    │   │
│   │ start OAuth      │   │ start OAuth      │   │ encrypt / decrypt  │   │
│   │ handle callback  │   │ handle callback  │   │ make / check state │   │
│   │ refresh token    │   │ list channels    │   │ map errors to HTTP │   │
│   │ list events      │   │ send message     │   │ health check       │   │
│   │ create event ────┼───┼─► notify()       │   │                    │   │
│   └────────┬─────────┘   └────────┬─────────┘   └────────────────────┘   │
│            │                      │                                      │
│   ┌────────▼──────────────────────▼──────────────────────────────────┐   │
│   │  DATABASE   (SQLite now, PostgreSQL later)                       │   │
│   │                                                                  │   │
│   │   GoogleCredential    access token*, refresh token*, expiry,     │   │
│   │                       which scopes were granted                  │   │
│   │   SlackInstallation   bot token*, workspace id, workspace name,  │   │
│   │                       bot user id, which scopes were granted     │   │
│   │   EventNotification   google event id, channel id, status        │   │
│   │                       (this table is how we avoid duplicates)    │   │
│   │                                                                  │   │
│   │   * = encrypted before it is written, and never written to logs  │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Secrets come from environment variables, loaded from backend/.env:      │
│    GOOGLE_CLIENT_ID    GOOGLE_CLIENT_SECRET                              │
│    SLACK_CLIENT_ID     SLACK_CLIENT_SECRET                               │
│    TOKEN_ENCRYPTION_KEY    DJANGO_SECRET_KEY                             │
└───────────┬──────────────────────────────────────┬───────────────────────┘
            │                                      │
            │ HTTPS, server to server              │ HTTPS, server to server
            ▼                                      ▼
┌───────────────────────────────┐    ┌─────────────────────────────────────┐
│  GOOGLE                       │    │  SLACK                              │
│                               │    │                                     │
│  accounts.google.com          │    │  slack.com/oauth/v2/authorize       │
│    /o/oauth2/v2/auth          │    │    (the install page)               │
│      (the consent page)       │    │  slack.com/api/oauth.v2.access      │
│  oauth2.googleapis.com/token  │    │    (swap code for token)            │
│    (swap code for token,      │    │  slack.com/api/conversations.list   │
│     and refresh later)        │    │    (list channels)                  │
│  www.googleapis.com           │    │  slack.com/api/chat.postMessage     │
│    /calendar/v3/...           │    │    (send a message)                 │
│      (read and write events)  │    │                                     │
└───────────────────────────────┘    └─────────────────────────────────────┘
```

---

## Three things to notice in that diagram

### Every arrow to Google or Slack starts at our backend

Look at the bottom half. There are no arrows going from the browser directly to
Google's API or Slack's API. That is on purpose.

You may be thinking: but the user *does* visit a Google page when they click
Connect Google. True — but that is the browser *navigating* to a web page, the
same as typing an address in the address bar. It is not our code making an API
call. The distinction matters, and document 03 explains why.

### The trust boundary is a real line, not a metaphor

Everything below the "OUR BACKEND" line can hold secrets. Everything above it
cannot. The reason is simple and has nothing to do with discipline:

Code running in a browser can be read by the person using that browser. They can
open developer tools, look at the network tab, read the JavaScript bundle, and
inspect every value in memory. There is no way to hide a secret inside a web
page. None. If your React app contains your Google client secret, then every
visitor to your site has your Google client secret.

So the rule is not "be careful with secrets in the frontend." The rule is "there
are no secrets in the frontend."

### The two integrations touch in exactly one place

Find the dashed arrow: `create event ──► notify()`.

That single function call is the only place where the Google side of the app and
the Slack side of the app know about each other. Everything else is independent.

This is a deliberate design decision and it pays off in several ways. We can
build and test the whole Slack integration in Phase 3 without the Google code
existing. We can break Slack completely and Google still works. And when we get
to Phase 4, connecting them is a small, understandable change rather than a
rewrite.

When you hear people talk about "loose coupling," this is what they mean in
practice. Not a design pattern — just keeping the number of places two things
touch as small as you can.

---

## What the frontend is responsible for

The frontend has one job: **make the system pleasant to use.**

Concretely, it:

- Draws the interface.
- Collects what the user types.
- Does quick, friendly validation — telling the user "end time must be after
  start time" the moment they type it, rather than after a round trip.
- Shows loading spinners so the app does not look frozen while it waits.
- Shows success, warning and error messages in a readable way.
- Remembers what the user has selected while they are on the page.

And here is what it is explicitly **not** responsible for:

- It does not decide what is allowed. It cannot. Anyone can bypass your React app
  entirely and send requests straight to your backend with `curl`. If your only
  check lives in the frontend, you have no check at all.
- It does not hold credentials.
- It does not talk to Google or Slack.
- It does not know how OAuth works. It just sends the user to a URL the backend
  gave it.

The frontend's validation is a **courtesy**. The backend's validation is the
**rule**. You need both, and they are not duplicated effort — they exist for
different reasons. One improves the experience; the other protects the system.

---

## What the backend is responsible for

The backend has the harder job. It:

- **Holds all the secrets** and makes sure they never leave.
- **Decides what is allowed.** Every request is validated here, properly, as
  though the frontend did not exist.
- **Talks to Google and Slack**, including knowing their URLs, their required
  parameters, and their error formats.
- **Manages tokens over time** — storing them, encrypting them, noticing when
  they are about to expire, refreshing them, and handling the case where they
  have been revoked.
- **Decides the order of operations** when more than one thing must happen.
- **Translates confusing third-party errors into messages a human can act on.**
  Slack saying `missing_scope` is useless to a user. "Please reinstall the Slack
  app so it can be granted permission to read channels" is useful. Doing that
  translation is real work and it belongs here.
- **Keeps a record** of what happened, which is both an audit trail and how we
  avoid sending duplicate notifications.

---

## Why two servers during development

You will run two processes while building this:

```
Terminal 1:   cd backend   →  python manage.py runserver     →  port 8000
Terminal 2:   cd frontend  →  npm run dev                    →  port 5173
```

This feels odd at first. Why not one?

Because during development each tool gives you something valuable. Vite on 5173
reloads your React app the instant you save a file, which makes frontend work
fast. Django on 8000 reloads your Python code when you save, and prints a useful
request log.

The cost is that the browser now sees two different origins — `localhost:5173`
and `localhost:8000` — and browsers deliberately restrict pages from calling
other origins. That restriction is called the same-origin policy, and the
mechanism for allowing specific exceptions is called **CORS**, Cross-Origin
Resource Sharing.

We will configure Django in Phase 1 to say "requests from `http://localhost:5173`
are allowed, and may include cookies." Everything else stays blocked. This is a
common source of confusion for beginners, so we will do it early, deliberately,
and I will explain each setting as we add it.

In production you would typically serve the built React files from the same
origin as the API, and the CORS question disappears entirely. Document 10 covers
that.

---

## Why Django, React and this particular stack

Short version, since you asked for the stack in your brief and I agree with it:

**Django** gives us a database layer, migrations, a session framework, an admin
panel and a settings system without us building any of it. For a project about
integration, we want the surrounding plumbing to be boring and already solved.

**Django REST Framework** sits on top of Django and handles the repetitive parts
of building a JSON API: validating incoming data, turning Python objects into
JSON, and producing sensible error responses.

**React with TypeScript.** React because it is the most common choice you will
meet in a job. TypeScript because when you are calling an API whose responses
have a specific shape, having the compiler tell you "that field does not exist"
catches a real category of mistake before you run the code.

**SQLite to start, PostgreSQL later.** SQLite needs zero setup; it is a file. The
Django code we write is identical either way, so switching is a configuration
change, which we will do in Phase 6 so you have seen it.

**Plain HTTP requests instead of Google's and Slack's official SDK libraries.**
This one deserves explaining, because it is the opposite of what you would do at
work.

Those libraries are good. In a real job, use them. But they hide exactly the part
you are here to learn. `google-api-python-client` will refresh your access token
automatically, in the background, without you ever seeing the request. That is
convenient and it is also the single most important thing in document 04.

So we will write the token exchange and the refresh by hand, once, with the
`requests` library. After that, you will know precisely what those SDKs are doing
for you — which means you will be able to debug them when they misbehave, and you
will be able to integrate a service that has no SDK at all. That is the skill
worth having.

---

Next: [03 — OAuth Explained Simply](03-oauth-explained.md)
