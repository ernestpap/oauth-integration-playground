# 10 — Security Notes

This document has two halves.

The first half is the things we do properly from the start, because they are not
much harder than doing them badly and they are the habits worth forming.

The second half is an honest list of the shortcuts we take, what each one would
have to become before this app faced the public internet, and why the shortcut is
acceptable for now.

Being able to tell those two categories apart is itself a professional skill. The
unhelpful answers are "it is just a demo, security does not matter" and "we must
do everything perfectly before we learn anything." Neither is how real work goes.

---

## Part 1: What we do properly

### Secrets live in environment variables, never in code

Every secret is read from `backend/.env`, which git ignores.

This protects against a specific, extremely common accident: pushing credentials
to a public repository. Automated scanners trawl GitHub continuously, and
exposed cloud credentials have been found and abused within **minutes** of being
pushed.

It also makes the same code deployable to different environments — development,
staging, production — each with its own values and no code changes.

**If you ever do commit a secret**, the fix is not to delete the file and commit
again. Git keeps history; the secret is still there and anyone who clones the
repository gets it. The fix is to **revoke that credential and issue a new one**,
on the assumption that it has already been taken. Both Google and Slack let you
rotate a client secret in a couple of clicks. Do that, then clean up the history
if you like, in that order.

### `.gitignore` is written before `.env` exists

Document 07 covers this. The order is the whole point: a file git has never seen
cannot accidentally be committed.

### The frontend holds nothing sensitive

`frontend/.env.example` contains exactly one line, and it is our own backend's
address.

This is not caution, it is a property of the medium. Code that runs in a browser
can be read by whoever is using that browser — developer tools, network tab,
view-source, the JavaScript bundle itself. There is no mechanism for hiding a
value inside a web page.

Vite makes this explicit in a way I like: only variables prefixed `VITE_` are
exposed to your frontend code, and anything with that prefix is compiled into the
bundle you ship. The prefix is a speed bump that makes you decide, consciously,
to publish something.

### Tokens are encrypted before they are stored

Access tokens, refresh tokens and bot tokens are encrypted with Fernet before
being written to the database, and decrypted only at the moment of use.

What this protects against: somebody obtaining a copy of your database file, or a
database backup, or a dump from a SQL injection flaw. They get ciphertext.

What it does **not** protect against: somebody who can run code on your server.
They can read the key out of the environment and decrypt everything. Encryption
at rest is a real control with real limits, and it is worth being clear about
both halves of that sentence rather than treating encryption as a magic word.

### Every OAuth flow validates `state`

Both flows generate a random value, store it server-side in the session, and
reject any callback that does not match. Written once in
`integrations/oauth_state.py`, used twice.

Document 03 describes the login-CSRF attack this prevents in detail. It is one of
the few genuine security mechanisms you will implement in this project with your
own hands, which makes it worth understanding rather than copying.

### We request the minimum scopes

Google: `calendar.events` and nothing else. Not `calendar`, which would allow
deleting entire calendars and changing sharing settings.

Slack: `channels:read`, `chat:write`, `chat:write.public`. Not `users:read`, not
`channels:history`, not `files:write`.

The benefit is that a bug or a leak can only cause damage within what we asked
for. We cannot delete somebody's calendar if we never had permission to delete
calendars. Least privilege is less about trust and more about bounding the size
of your worst day.

### We never log credentials

No token, no client secret, no authorization code gets written to a log file or
printed to the terminal.

This sounds obvious and is violated constantly, usually by accident:

```python
logger.info("Token exchange response: %s", response.json())   # just logged a
                                                              # refresh token
print(f"Calling Google with {headers}")                       # and again
except Exception as e:
    logger.error(f"Request failed: {request.url}")            # the code is in
                                                              # that URL
```

Logs feel transient and private. They are neither. They get shipped to log
aggregation services, retained for years, read by support staff, and included in
bug reports. A secret in a log is a secret in a dozen systems you did not think
about.

Our rule: log the *shape* of things, not their contents. "Token refresh
succeeded, expires in 3599s" tells you everything useful for debugging and
reveals nothing.

### Validation happens on the backend regardless of the frontend

Every endpoint validates its input as though the React app did not exist, because
anybody can send a request directly with `curl`. The frontend's validation is
there to make the app feel responsive, and it is genuinely worth having — it is
just not a security control.

### Errors are specific internally and vague externally

`missing_scope` is useful to us. The user needs "reinstall the Slack app to grant
permission to read channels." And neither of those is the same as leaking
internal detail — we never return a stack trace, a database error, or a raw
provider response to the client.

---

## Part 2: Our shortcuts, and what they would become

This is the honest list. Nine shortcuts, each with what it is, why it is
acceptable now, and what production requires.

### 1. The encryption key sits in `.env` next to the data it protects

**Now:** `TOKEN_ENCRYPTION_KEY` is a line in a file on the same machine as
`db.sqlite3`.

**Why it is acceptable:** it is your machine, the data is your own test calendar,
and it still genuinely protects against the realistic local accident of
committing or sharing the database file.

**Production:** the key belongs in a dedicated secret manager — AWS KMS, Google
Cloud KMS, HashiCorp Vault, Azure Key Vault. The application asks the service to
decrypt and never holds the key material itself. You also want a **key rotation**
plan: a scheme where tokens record which key version encrypted them, so you can
introduce a new key without invalidating existing data. This is a real design
task, not a configuration setting.

### 2. `DEBUG = True`

**Now:** Django's debug mode shows a detailed error page with a stack trace,
local variables and settings when something fails. Excellent for learning.

**Production:** `DEBUG = False`, absolutely without exception. That error page
exposes your code, your file paths, your installed packages and sometimes your
environment variables to anybody who can trigger an exception. It is one of the
most reliable ways to leak a configuration. You must also set `ALLOWED_HOSTS` to
your real domains, because Django refuses to start with `DEBUG = False` and an
empty list — a safety feature rather than an annoyance.

### 3. Plain HTTP on localhost

**Now:** everything is `http://localhost`. Traffic never leaves your machine, so
there is no network to eavesdrop on.

**Production:** HTTPS everywhere, no exceptions. Without it, session cookies and
authorization codes travel in plain text across networks you do not control.
Google and Slack both *require* HTTPS redirect URIs for anything other than
localhost, so you will not have the choice. Specifically, you need:

```python
SECURE_SSL_REDIRECT = True          # send HTTP traffic to HTTPS
SESSION_COOKIE_SECURE = True        # only send the session cookie over HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True      # JavaScript cannot read the cookie
SESSION_COOKIE_SAMESITE = "Lax"     # limits cross-site cookie sending
SECURE_HSTS_SECONDS = 31536000      # tell browsers to insist on HTTPS
```

`SESSION_COOKIE_HTTPONLY` is worth a sentence. It means a cross-site scripting
flaw cannot steal the session cookie with JavaScript. It costs nothing, since our
frontend never needs to read that cookie.

### 4. One user, no login

**Now:** one `GoogleCredential` row, one `SlackInstallation` row. The app assumes
a single person is using it.

**Why it is acceptable:** authentication is a large topic of its own, and
including it would have diluted the integration lesson you came for.

**Production:** every credential row needs a foreign key to a user, every lookup
needs filtering by the current user, and the app needs real authentication. The
failure mode if you get this wrong is severe and worth naming: **one user seeing
another user's calendar.** That class of bug — missing a filter on a query — is
one of the most common serious vulnerabilities in real web applications. It has a
name, IDOR, and it almost always looks like forgetting one `WHERE` clause.

I will point out the exact lines where the foreign key would go when we write
them.

### 5. CORS allows a specific localhost origin

**Now:** `CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]`, with credentials
permitted.

**Production:** your real frontend domain, and nothing else. Two things never to
do: `CORS_ALLOW_ALL_ORIGINS = True` alongside credentialed requests, which lets
any website make authenticated calls to your API using your users' cookies; and
reflecting the request's `Origin` header back in the response, which is the same
mistake wearing a disguise.

Better still, serve the built frontend from the same origin as the API, and the
question disappears.

### 6. Synchronous Slack notification, with no retry

**Now:** the user waits for Slack, and a failure is recorded but never retried.

**Production:** hand the notification to a background worker — Celery with Redis,
or a managed queue — and return to the user as soon as Google has succeeded. Then
retry failures with exponential backoff, and with a cap, and with a dead-letter
queue for messages that will never succeed.

Document 06 explains why the `EventNotification` table is already the right shape
for this: every `status="failed"` row is a job waiting to exist.

### 7. SQLite

**Now:** a file on disk. Zero setup.

**Production:** PostgreSQL. SQLite's limitations matter under real use —
restricted concurrent writes, weaker constraint handling in some cases, and no
practical way to run multiple application servers against it. We will switch in
Phase 6 so you see that it is a settings change, not a code change.

### 8. The OAuth consent screen is unverified

**Now:** Testing mode, with the "unverified app" warning and the seven-day
refresh token expiry.

**Production:** submit for Google's verification. For sensitive scopes this
involves a privacy policy, a demo video, a security questionnaire and a wait of
several weeks. Worth knowing about now so it does not surprise you: for a real
product, this is a scheduling consideration, not an afternoon's work.

### 9. No rate limiting on our own API

**Now:** anyone who can reach your backend can call it as often as they like.
Fine, since that is only you.

**Production:** rate limit your own endpoints — DRF has throttling built in. Two
reasons. One, to stop abuse of your service. Two, and more subtly, to protect
your *upstream quota*: without a limit of your own, a single misbehaving client
can burn through your Google or Slack rate limit and take the integration down
for all your users. Your rate limit protects your relationship with your
providers as much as it protects your server.

---

## Part 3: A summary table

| Concern | Our demo | Production |
|---|---|---|
| Secrets | `.env` file | Secret manager (KMS, Vault) |
| Token encryption key | In `.env` | In KMS, with a rotation plan |
| `DEBUG` | `True` | `False`, with `ALLOWED_HOSTS` set |
| Transport | HTTP on localhost | HTTPS, HSTS, secure cookies |
| Users | One, no login | Real auth, per-user credential rows |
| CORS | `localhost:5173` | Exact frontend domain, or same origin |
| Slack delivery | Synchronous, no retry | Background queue with backoff |
| Database | SQLite | PostgreSQL |
| Google app status | Testing, unverified | Verified |
| Our own rate limits | None | DRF throttling |
| Logging | Terminal, no secrets | Aggregated, no secrets, with alerts |
| Error detail to client | Generic messages | Same — this one does not change |

That last row is deliberate. Most of this table describes things we are doing
simply because it is a demo. Not logging secrets and not leaking internal detail
to clients are not in that category — they are the same in both columns, which is
why they belong in Part 1 rather than here.

---

## Part 4: Three habits worth more than any checklist

If you take three things from this document into every future project:

**Assume your database will be stolen, and design so that it matters less.** This
is why tokens are encrypted and why least-privilege scopes are worth the thought.
Not paranoia — just planning for a scenario that happens to real companies every
week.

**Assume your logs will be read by someone you did not expect.** This is why
secrets never go in them. Logs outlive the incident they were written for.

**Assume somebody will bypass your frontend entirely.** This is why validation
and authorisation live on the backend. The browser is a convenience you offer
users, not a gate you control.

Each of those is a single sentence, and between them they prevent a remarkable
share of real-world security incidents.

---

Next: [11 — Glossary](11-glossary.md)
