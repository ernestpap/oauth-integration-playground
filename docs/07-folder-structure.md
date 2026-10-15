# 07 — Folder Structure

Here is every folder and file we are going to create, and why each one exists.
Nothing has been created yet except these documents — this is the plan.

Read this before Phase 1.

---

## The whole tree

```
D:\work\learn by doing\
│
├─ README.md                     how to set up and run the project
├─ .gitignore                    what git must never record
│
├─ docs/                         these documents
│  ├─ 00-start-here.md
│  ├─ 01-what-we-are-building.md
│  ├─ ... and so on
│
├─ backend/                      the Django server. Holds all secrets.
│  │
│  ├─ manage.py                  Django's command-line entry point
│  ├─ requirements.txt           the Python packages we depend on
│  ├─ .env.example               the NAMES of required secrets. Committed.
│  ├─ .env                        the REAL secrets. Never committed.
│  ├─ db.sqlite3                 the database. Never committed.
│  │
│  ├─ config/                    project-wide settings, not features
│  │  ├─ __init__.py
│  │  ├─ settings.py             reads .env, configures Django, CORS, apps
│  │  ├─ urls.py                 the top-level routing table
│  │  ├─ wsgi.py                 entry point for production servers
│  │  └─ asgi.py                 entry point for async production servers
│  │
│  ├─ integrations/              shared plumbing used by both integrations
│  │  ├─ __init__.py
│  │  ├─ crypto.py               encrypt() and decrypt() for stored tokens
│  │  ├─ oauth_state.py          create and verify the `state` parameter
│  │  ├─ errors.py               our own exception types, and how they map
│  │  │                          onto HTTP responses
│  │  ├─ views.py                /api/health/ and /api/status/
│  │  └─ urls.py
│  │
│  ├─ google_calendar/           everything Google, and nothing else
│  │  ├─ __init__.py
│  │  ├─ models.py               GoogleCredential
│  │  ├─ migrations/             generated database change scripts
│  │  ├─ oauth.py                build consent URL, exchange code, refresh
│  │  ├─ client.py               a thin wrapper over the Calendar API
│  │  ├─ serializers.py          validation of incoming event data
│  │  ├─ views.py                the four endpoints
│  │  ├─ urls.py
│  │  └─ tests/
│  │     ├─ test_oauth.py
│  │     └─ test_client.py
│  │
│  └─ slack_app/                 everything Slack, and nothing else
│     ├─ __init__.py
│     ├─ models.py               SlackInstallation, EventNotification
│     ├─ migrations/
│     ├─ oauth.py                build install URL, exchange code
│     ├─ client.py               conversations.list, chat.postMessage
│     ├─ notifications.py        notify_event_created() — the single seam
│     ├─ views.py
│     ├─ urls.py
│     └─ tests/
│        ├─ test_oauth.py
│        ├─ test_client.py
│        └─ test_notifications.py
│
└─ frontend/                     the React app. Holds no secrets.
   │
   ├─ package.json               JavaScript dependencies and scripts
   ├─ vite.config.ts             dev server configuration
   ├─ tsconfig.json              TypeScript compiler settings
   ├─ index.html                 the single HTML page everything loads into
   ├─ .env.example               one non-secret variable: the API base URL
   │
   └─ src/
      ├─ main.tsx                mounts React into index.html
      ├─ App.tsx                 overall layout
      │
      ├─ api/
      │  ├─ client.ts            the only file that knows our backend's URLs
      │  └─ types.ts             TypeScript types mirroring the API's JSON
      │
      ├─ components/
      │  ├─ IntegrationStatus.tsx    connected / not connected, and buttons
      │  ├─ UpcomingEvents.tsx       the list of events
      │  ├─ CreateEventForm.tsx      the form
      │  ├─ ChannelPicker.tsx        the Slack channel dropdown
      │  └─ Alert.tsx                success, warning and error messages
      │
      └─ hooks/
         └─ useIntegrationStatus.ts  fetches and holds connection status
```

---

## Why backend and frontend are separate folders

They are two different programs, in two different languages, run by two different
commands, with two different dependency systems. Python packages in
`requirements.txt`, JavaScript packages in `package.json`. Keeping them in
separate folders keeps those worlds from tangling.

It also makes the trust boundary visible in the filesystem. There is one folder
where secrets live and one where they must never appear. When you are about to
add something sensitive, the path you are typing tells you whether you are making
a mistake.

---

## The backend, folder by folder

### `config/` — the project, not the features

Django distinguishes between a **project** and an **app**. The project is the
overall configuration: which database, which installed apps, which settings. An
app is a self-contained piece of functionality.

`config/` is the project. Three files in it matter to us.

**`settings.py`** is the single place that reads environment variables. Nothing
else in the codebase calls `os.environ` — everything imports from settings. That
way, when you want to know what configuration this project needs, there is one
file to read.

**`urls.py`** is the top-level routing table. It does not define endpoints
itself; it delegates:

```python
urlpatterns = [
    path("api/", include("integrations.urls")),
    path("api/", include("google_calendar.urls")),
    path("api/", include("slack_app.urls")),
]
```

So each app owns its own URLs, and this file just says where to look. Adding an
integration later means adding one line here.

**`wsgi.py` and `asgi.py`** are production entry points. We will not touch them,
but it is worth knowing they exist: `manage.py runserver` is a development server
and is explicitly not meant for real traffic. In production something like
Gunicorn imports `wsgi.py` instead.

### `integrations/` — the shared plumbing

This folder exists for one reason: **both integrations need the same security
code, and two copies of security code is a liability.**

`crypto.py` holds `encrypt()` and `decrypt()`. Google tokens and Slack tokens go
through the same functions.

`oauth_state.py` holds the generation and verification of the `state` parameter.
Both OAuth flows need identical CSRF protection. If we wrote it twice, then one
day somebody would fix a subtle issue in one copy and not the other, and the
weaker copy would quietly remain in production. One implementation, used twice,
cannot drift.

`errors.py` defines our own exception types — things like
`IntegrationNotConnected`, `TokenExpired`, `SlackPermissionDenied` — plus the
logic that turns them into HTTP responses with helpful messages.

This is worth a moment, because it is a pattern you will reuse. Deep inside
`client.py` you know exactly what went wrong but have no business deciding what
HTTP status to return. Up in the view you know about HTTP but have lost the
detail. So the client raises a specific, meaningful exception, and one handler in
the view layer maps exception types onto status codes and user-facing messages.
Each layer does the job it is in a position to do.

### `google_calendar/` and `slack_app/` — one app per integration

Each is a self-contained Django app. You could delete one and the other would
keep working, apart from the single function call described in document 06.

Why split them this way rather than having, say, an `oauth/` folder and an
`api_clients/` folder?

Because **things that change together should live together.** When Slack changes
its API, you edit files in `slack_app/`. When you are debugging a Slack problem,
everything relevant is in one directory. The alternative organisation — grouping
by technical role instead of by feature — means a single change touches four
folders and understanding one integration means reading all of them.

The naming is slightly awkward on purpose. The folder is `slack_app` rather than
`slack` because a top-level module named `slack` can collide with Slack's own
published package name. Similarly `google_calendar` rather than `google`, since
`google` is a real namespace used by Google's Python libraries. Avoiding
accidental shadowing of installed packages is a small habit that saves a baffling
afternoon.

### The four files inside each integration app

This is the split that matters most, so here it is in detail.

**`models.py`** — what we store. Database tables, as Python classes.

**`oauth.py`** — the authorization dance. Building the URL the user visits,
exchanging the code for tokens, and (for Google) refreshing them.

**`client.py`** — talking to the API once we have a token. For Google: list
events, create event. For Slack: list channels, post message. This file knows the
third party's URLs, parameters and error formats, and it translates their errors
into our own exception types.

**`views.py`** — HTTP. Read the request, call a function from `oauth.py` or
`client.py`, shape a response. Views should be short. If a view is long,
something that belongs in a client or a serializer has leaked into it.

#### Why this split is worth the extra files

The honest answer is **testability**, and it is easier to see with an example.

Suppose everything lived in `views.py`. To test "do we handle an expired token
correctly," you would have to construct a fake HTTP request, run it through
Django's whole request cycle, intercept the outgoing network call, and inspect an
HTTP response.

With the split, the refresh logic is a plain function in `oauth.py`. You call it
directly with a stored credential, fake Google's reply, and assert on what got
saved. No HTTP involved on either side. The test is five lines and it tells you
one specific thing.

Phase 6 is short because of decisions made in Phase 2. That is generally how
testing works: the difficulty of testing code is mostly determined before you
write the first test.

**`serializers.py`** deserves a note too, because it is a Django REST Framework
idea you may not have met. A serializer does two jobs: validating incoming JSON,
and converting Python objects to JSON for responses. Our event serializer is
where "end time must be after start time" and "attendees must be valid email
addresses" live. Keeping validation in a declared schema rather than scattered
`if` statements in a view means the rules are all in one readable place.

---

## The frontend, folder by folder

### `src/api/` — the only folder that knows backend URLs

Every call to our backend goes through `client.ts`. No component ever calls
`fetch()` directly.

Three benefits.

**One place to change.** Rename an endpoint and you edit one file.

**One place for cross-cutting concerns.** Sending cookies with every request,
parsing error responses into a consistent shape, setting the base URL from an
environment variable — each of these is written once instead of in every
component.

**One place for the contract.** `types.ts` holds TypeScript types that mirror
what the backend returns:

```typescript
export type SlackNotificationStatus = "sent" | "failed" | "skipped";

export interface CreateEventResponse {
  event: CalendarEvent;
  slack: {
    status: SlackNotificationStatus;
    channel?: string;
    error?: string;
    hint?: string;
  } | null;
}
```

Writing that type out has a nice side effect: it forces you to be explicit about
the three outcomes from document 06. A component handling this response cannot
accidentally forget the `"failed"` case, because TypeScript will point out the
missing branch.

### `src/components/` — one file per visible thing

Small components, each responsible for one part of the screen. `Alert.tsx` is the
one worth calling out: by having a single component that renders success, warning
and error states, every message in the app looks consistent, and the amber
"partial success" case from document 06 has an obvious home.

### `src/hooks/` — shared stateful logic

`useIntegrationStatus.ts` fetches whether Google and Slack are connected and
makes that available to any component that needs it. Several parts of the UI care
about connection status — the status panel, the form (which should be disabled
when Google is not connected), the channel picker — so the fetching logic lives
in one place rather than in three.

---

## The files about secrets

These four deserve their own section, because getting them wrong is the mistake
with the worst consequences.

### `.gitignore` — created first, before anything else

```
backend/.env
backend/db.sqlite3
backend/venv/
backend/__pycache__/
*.pyc
frontend/node_modules/
frontend/dist/
.DS_Store
```

We will create this in **Phase 1, before `.env` exists.** The order is
deliberate, and here is why.

Git tracks files you have added. Once a file is committed, it is in the
repository's history permanently — adding it to `.gitignore` afterwards stops
future changes being tracked but does **not** remove it from history. Anyone who
clones the repository gets every version of that file that was ever committed.

If you commit a secret and then push it to GitHub, the correct response is not to
delete the file. It is to **revoke that secret and issue a new one**, because you
must assume it has been harvested. Automated scanners find exposed credentials in
public repositories within minutes.

So: `.gitignore` first. It costs nothing and removes the possibility.

### `.env` — the real secrets, never committed

```
DJANGO_SECRET_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/google/oauth/callback/
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
SLACK_REDIRECT_URI=http://localhost:8000/api/slack/oauth/callback/
TOKEN_ENCRYPTION_KEY=...
FRONTEND_URL=http://localhost:5173
```

Notice that the redirect URIs are variables rather than being written into the
code. Document 04 explained that these must match the provider's registered value
exactly. Having one source for the value means there is only one copy to get
wrong, and when you change it you change it once.

### `.env.example` — the shape of the secrets, committed

```
DJANGO_SECRET_KEY=replace-me-with-a-long-random-string
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
...
```

Same keys, placeholder values. This is for whoever clones the repository
afterwards — including you, in six months, on a different machine. It answers
"what configuration does this project need?" without exposing anything.

It also serves as documentation that stays current, because a missing variable
breaks the app immediately and gets noticed.

### `frontend/.env.example` — almost empty

```
VITE_API_BASE_URL=http://localhost:8000
```

That is the whole file, and the emptiness is the point. The frontend's
configuration contains exactly one value, and it is not a secret.

One Vite-specific trap worth knowing: only variables prefixed `VITE_` are exposed
to your frontend code, and anything with that prefix is **baked into the
JavaScript bundle** that you ship to browsers. So if you ever put a secret in a
`VITE_`-prefixed variable, you have published it. The prefix requirement is
deliberately there to make you think before exposing something.

---

## How to run it

Two terminals, left open while you work:

```
Terminal 1 — backend
    cd backend
    .\venv\Scripts\activate          (Windows PowerShell)
    python manage.py runserver
    → http://localhost:8000

Terminal 2 — frontend
    cd frontend
    npm run dev
    → http://localhost:5173
```

You open `http://localhost:5173` in your browser. That page calls the backend on
port 8000.

Both servers reload automatically when you save a file, so you will rarely need
to restart them. The exceptions, worth remembering now so they do not confuse you
later: changes to `.env` and changes to `settings.py` are read at startup, so
those **do** require stopping and restarting Django. "I changed the value and
nothing happened" is almost always this.

---

Next: [08 — Accounts and Setup](08-prerequisites-setup.md)
