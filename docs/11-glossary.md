# 11 — Glossary

Every piece of jargon in this project, explained in plain language. Dip into it
whenever a word stops you.

Organised by topic rather than alphabetically, because related terms are easier
to understand next to each other.

---

## OAuth and authorization

**OAuth 2.0** — The standard way for an app to get limited permission to use your
account on another service, without ever seeing your password. The hotel key card
rather than the master key.

**Authentication vs authorization** — Authentication is *who are you*.
Authorization is *what are you allowed to do*. OAuth is primarily about the
second. People shorten both to "auth," which is why the distinction gets muddled.

**Resource owner** — The person who owns the data. You, when it is your calendar.

**Client** — The application asking for access. Our Django app. Confusingly, the
"client" in OAuth is a server, not a browser.

**Authorization server** — The service that asks the user for consent and issues
tokens. Google's and Slack's login pages.

**Resource server** — The API that holds the actual data. The Google Calendar
API. Often the same company as the authorization server, but a different concern.

**Three-legged OAuth** — Shorthand for the fact that three parties are involved:
the user, the app, and the provider. "Two-legged" refers to server-to-server
flows with no user present.

**Authorization code** — A short-lived, single-use ticket that travels back
through the browser after you click Allow. Deliberately useless on its own:
redeeming it requires the client secret, which only our backend has.

**Client ID** — The public name for our app. Appears in URLs. Not a secret.

**Client secret** — The value that proves we really are that app. Backend only,
forever, with no exceptions. If it leaks, revoke it.

**Access token** — A short-lived key sent with every API call. Google's last
about an hour.

**Refresh token** — A long-lived key used only to obtain new access tokens. Never
sent to the API itself, only to the token endpoint. The valuable one.

**Bearer token** — A token where mere possession is sufficient to use it, with no
further proof required. Sent as `Authorization: Bearer <token>`. The name is the
warning: whoever bears it can use it.

**Bot token** (`xoxb-`) — A Slack token representing the app's own identity in a
workspace. What we use.

**User token** (`xoxp-`) — A Slack token that acts as a specific person. Not what
we use.

**Scope** — One named permission, such as `calendar.events` or `chat:write`.
Shown to the user on the consent screen before they agree.

**Least privilege** — The principle of asking for the minimum permissions you
need. Limits the damage of any bug or leak.

**Consent screen** — The provider-hosted page listing what an app wants and
offering Allow or Deny.

**Redirect URI** (also *callback URL*) — The exact address the provider is
allowed to send the user back to. Must be pre-registered, and matched character
for character.

**`state` parameter** — A random value we generate, store server-side, send to
the provider, and verify when the user returns. Proves the callback belongs to a
flow we started.

**Token rotation** — A scheme where long-lived tokens are periodically replaced.
Google does this with refresh tokens; Slack offers it optionally for bot tokens.

**Revocation** — A user withdrawing permission. Afterwards your tokens stop
working, which you must handle gracefully rather than retrying.

---

## Web and HTTP

**API** — Application Programming Interface. A set of URLs another program can
call to read or change data. A website for software rather than for people.

**REST** — A common style for HTTP APIs: nouns in the URL, verbs as HTTP methods,
`GET /events/` to read and `POST /events/` to create.

**Endpoint** — One specific URL plus method that an API offers, such as
`POST /api/calendar/events/`.

**HTTP methods** — `GET` reads something, `POST` creates something, `PUT` and
`PATCH` update, `DELETE` removes. A `GET` should never change anything.

**Status code** — The three-digit number in a response. `2xx` worked, `3xx`
redirect, `4xx` you got it wrong, `5xx` the server got it wrong.

| Code | Meaning | When we use it |
|---|---|---|
| 200 | OK | Successful read |
| 201 | Created | Event created successfully |
| 302 | Found | Redirect, as in the OAuth flow |
| 400 | Bad Request | Invalid input, or a `state` mismatch |
| 401 | Unauthorized | Missing or invalid credentials |
| 403 | Forbidden | Authenticated but not permitted |
| 404 | Not Found | No such thing |
| 409 | Conflict | Integration not connected yet |
| 429 | Too Many Requests | Rate limited |
| 500 | Internal Server Error | We have a bug |
| 502 | Bad Gateway | An upstream service failed |

**Header** — A name-and-value pair carrying metadata about a request or response.
`Authorization`, `Content-Type`, `Retry-After`.

**Query parameter** — The part of a URL after `?`, such as `?maxResults=10`. Used
for filtering and options on `GET` requests.

**Request body** — The data sent with a `POST`. Usually JSON for us.

**JSON** — The text format APIs exchange data in: objects in braces, arrays in
brackets, strings in quotes.

**Redirect** — A response telling the browser to go somewhere else. The mechanism
that carries the user to Google and back.

**Cookie** — A small value the browser stores for a site and sends back with
every request. How Django recognises your session.

**Session** — Server-side storage tied to a browser via a cookie. Where we keep
the `state` value during an OAuth flow.

**CORS** — Cross-Origin Resource Sharing. The mechanism by which a server says
"pages from this other origin may call me." Needed because our frontend is on
port 5173 and our backend on 8000, which browsers treat as different origins.

**Same-origin policy** — The browser's default rule that a page may only call its
own origin. CORS is how you grant specific exceptions.

**Origin** — Scheme plus host plus port. `http://localhost:5173` and
`http://localhost:8000` are different origins despite both being localhost.

**HTTPS / TLS** — Encrypted HTTP. Required in production, and required by Google
and Slack for any redirect URI other than localhost.

**Rate limit** — A cap on how often you may call an API. Exceeding it gets you
`429` and usually a `Retry-After` header saying when to come back.

**`Retry-After`** — A response header giving the number of seconds to wait before
retrying. Honour it exactly.

**Pagination** — Returning results in pages rather than all at once.

**Cursor pagination** — A specific style where the response includes an opaque
pointer (`next_cursor`, `nextPageToken`) that you pass back to get the following
page. Used by both Slack and Google.

**Idempotent** — An operation where doing it twice has the same effect as doing
it once. What we make our Slack notification, so a double-click cannot
double-post.

---

## Security

**Secret** — Any value that grants access and must stay private. Client secrets,
tokens, encryption keys.

**Environment variable** — A value supplied to a program by its environment
rather than written in its code. How we keep secrets out of git.

**`.env` file** — A local file of environment variables, loaded at startup.
Never committed.

**Encryption at rest** — Encrypting data before storing it, so a stolen database
yields ciphertext. Protects against a stolen file, not against a compromised
server.

**Fernet** — The specific encryption scheme we use, from Python's `cryptography`
library. Symmetric: one key both encrypts and decrypts.

**Ciphertext / plaintext** — Encrypted data, and readable data.

**CSRF** — Cross-Site Request Forgery. Tricking a user's browser into making a
request they did not intend, using credentials it already holds. The `state`
parameter defends the OAuth flow against a variant of this.

**Login CSRF / session fixation** — The specific attack `state` prevents:
connecting *the attacker's* account to *your* session. Described in document 03.

**XSS** — Cross-Site Scripting. Injecting JavaScript into a page other people
view. Why `SESSION_COOKIE_HTTPONLY` is worth setting.

**IDOR** — Insecure Direct Object Reference. Being able to read someone else's
data by changing an ID, usually because a query is missing a filter on the
current user. The thing to be most careful about if you add multi-user support.

**Trust boundary** — The line between code you control and code you do not. In
our architecture, the line between the backend and the browser.

**Attack surface** — The total set of ways a system can be interacted with, and
therefore attacked. Fewer scopes and fewer endpoints means less surface.

---

## Django and Python

**Django** — The Python web framework we use. Provides the database layer,
routing, sessions, migrations and settings.

**Django REST Framework (DRF)** — A library on top of Django for building JSON
APIs. Handles validation and serialisation.

**Project vs app** — In Django, a *project* is the overall configuration
(`config/`) and an *app* is a self-contained feature (`google_calendar/`,
`slack_app/`).

**Model** — A Python class representing a database table. One instance is one
row.

**Migration** — A generated script that changes the database schema to match your
models. You run `makemigrations` to create one and `migrate` to apply it.

**ORM** — Object-Relational Mapper. Lets you query the database with Python
instead of SQL. `GoogleCredential.objects.first()` rather than `SELECT * FROM...`.

**View** — The function that handles an HTTP request and returns a response. In
DRF, often a class.

**Serializer** — A DRF object that validates incoming JSON and converts Python
objects to JSON on the way out. Where "end must be after start" lives.

**URL pattern / routing** — The mapping from URL to view, in `urls.py`.

**`get_or_create`** — A Django method that fetches a row or creates it if absent,
returning the object and a boolean saying which happened. How we claim a
notification exactly once.

**Unique constraint** — A database rule that no two rows may share the same
values in given columns. What makes our deduplication reliable rather than
hopeful.

**Race condition** — A bug where the outcome depends on the timing of concurrent
operations. The gap between "check whether it exists" and "create it" is a
classic example.

**Virtual environment (`venv`)** — A private package directory for one project,
so projects cannot break each other's dependencies.

**`requirements.txt`** — The list of Python packages this project needs.

**pytest** — The test runner we use.

**Mock** — A stand-in for a real thing in a test. We mock Google's and Slack's
HTTP responses so tests are fast, offline and able to simulate failures on
demand.

---

## React and frontend

**React** — The JavaScript library we use to build the interface from components.

**TypeScript** — JavaScript with type annotations, checked before the code runs.
Catches mistakes like using a field that does not exist.

**Component** — A reusable piece of interface, written as a function returning
markup.

**Props** — The inputs a component receives from its parent.

**State** — Data a component holds that can change over time, causing a re-render.

**Hook** — A function starting with `use` that lets a component use React
features. `useState`, `useEffect`, and our own `useIntegrationStatus`.

**Vite** — The build tool and development server for the frontend. Reloads
instantly when you save.

**`fetch`** — The browser function for making HTTP requests.

**JSX / TSX** — The syntax that lets you write markup inside JavaScript or
TypeScript.

**Bundle** — The single compiled JavaScript file shipped to browsers. Anything
inside it is public, which is why no secret may go near it.

---

## Google Calendar specifics

**`summary`** — Google's name for the event title. Not `title`.

**`primary`** — An alias for the user's main calendar, usable in place of a
calendar ID.

**`singleEvents=true`** — Expands recurring events into individual occurrences
rather than returning a recurrence rule.

**`sendUpdates`** — Controls whether Google emails the attendees. Defaults to
`none`, so we set it to `all` explicitly.

**`htmlLink`** — A direct link to the event in Google Calendar's web interface.
What we put in the Slack message.

**RFC 3339** — The date and time format Google expects, looking like
`2026-10-20T15:00:00+05:30`.

**`invalid_grant`** — The error meaning your refresh token is dead. Revoked,
expired, or never valid. Requires reconnection; retrying cannot help.

---

## Slack specifics

**Workspace** — A Slack organisation. Identified by a team ID like `T04ABCDEFGH`.

**Channel ID** — The stable identifier for a channel, like `C04IJKLMNOP`. Use
this rather than the name, which can change.

**`ok` field** — The boolean every Slack API response contains. **Must** be
checked, because Slack returns HTTP 200 even when `ok` is `false`.

**Blocks / Block Kit** — Slack's rich message layout system. Headers, sections,
buttons.

**`text` fallback** — The plain-text summary required alongside `blocks`, used
for push notifications and screen readers.

**`missing_scope`** — You did not request a permission you need. Requires
reinstalling the app, not a code change.

**`not_in_channel`** — The bot is not a member of the channel and lacks
`chat:write.public`.

**App manifest** — A YAML description of a Slack app's configuration. A fast way
to create apps once you know what the settings mean; we configure by hand instead
so the settings are visible.

---

Next: [12 — Troubleshooting](12-troubleshooting.md)
