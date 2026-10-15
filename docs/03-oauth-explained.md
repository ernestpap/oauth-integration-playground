# 03 — OAuth Explained Simply

This is the most important document in the set. If OAuth clicks for you here,
Google and Slack become details rather than mysteries.

---

## The problem OAuth solves

Our app needs to read and write your Google Calendar. So, naively: ask you for
your Google email and password, log in as you, and get on with it.

Think about everything wrong with that.

**We would be able to do absolutely everything.** Not just your calendar. Your
Gmail. Your Drive. Your photos. Your YouTube account. The ability to change your
password and lock you out. A calendar app would be holding the keys to your
entire digital life.

**We would have to store your password.** Which means when our database is
eventually stolen — and databases do get stolen — your Google password is in the
hands of whoever took it. And because people reuse passwords, so is your bank
login.

**You could never take the permission back** without changing your password,
which would also break every other app you had given it to.

**You would have no idea what we were doing.** No record of which apps are
touching your account, or what they are touching.

**And it would break anyway**, the moment you turn on two-factor authentication.

So "just ask for the password" is not merely insecure — it does not actually
work. Something better is needed.

---

## The hotel analogy

OAuth is a hotel key card.

When you check into a hotel, you do not get the owner's master key. You go to the
front desk — the only place that is trusted with keys — prove who you are, and
receive a card that:

- opens **only** your room, the gym and the pool (limited permissions)
- stops working on your checkout date (it expires)
- can be cancelled from the front desk if you lose it (it can be revoked)
- is logged, so the hotel knows which card opened which door (it is auditable)

Now map that onto our app:

| Hotel | OAuth | In our project |
|---|---|---|
| You, the guest | The **resource owner** | You, the person whose calendar it is |
| The hotel guest wanting access | The **client** | Our Django app |
| The front desk | The **authorization server** | Google's login and consent pages |
| The rooms and facilities | The **resource server** | The Google Calendar API |
| The key card | The **access token** | A string beginning `ya29.` |
| "Room, gym, pool" | The **scopes** | `calendar.events` |

The crucial detail: **the guest never hands their identity documents to the
person asking for access.** You show your passport to the front desk, not to the
app. In OAuth, you type your Google password into a *Google* page. Our app never
sees it, never could see it, and never needs to.

This is why the pattern is sometimes described as **three-legged**. Three parties
are involved — you, our app, and Google — and the trust runs between you and
Google, not between you and our app.

---

## The flow, in plain words first

Here is the whole thing as a story, with no jargon.

1. You click **Connect Google** in our app.

2. Our backend builds a long Google URL that says, in effect: "Hello Google, I am
   app number 12345, I would like permission to manage this person's calendar
   events, and when you are done please send them back to this exact address."
   It sends your browser to that URL.

3. You land on a page hosted by **Google**. If you are not logged in, you log in
   — to Google, on Google's own page. Google then shows you what we are asking
   for and offers Allow or Deny.

4. You click Allow.

5. Google sends your browser back to our app's address, and tacks a short code
   onto the end of the URL. Something like
   `...?code=4/YOUR-ONE-TIME-CODE&state=xyz`.

6. Our backend takes that code and makes its own private request to Google, from
   server to server, which says: "Here is the code you just gave my user. Here is
   also my client secret, which proves I really am app 12345. Please exchange
   this for tokens."

7. Google checks the code and the secret, and replies with the tokens.

8. Our backend encrypts the tokens and saves them in the database.

9. Our backend sends your browser back to the app's page, which now says
   "connected."

From then on, whenever our app wants to touch your calendar, it attaches the
access token to its request and Google allows it.

---

## The same flow as a diagram

```
   You / Browser              Our Backend                      Google
        │                          │                              │
  (1)   │  click "Connect Google"  │                              │
        ├─────────────────────────►│                              │
        │                          │  make a random `state` value │
        │                          │  remember it in the session  │
        │                          │  build the consent URL       │
  (2)   │   "go to this Google URL"│                              │
        │◄─────────────────────────┤                              │
        │                                                          │
  (3)   │  GET accounts.google.com/o/oauth2/v2/auth?...            │
        ├─────────────────────────────────────────────────────────►│
        │                                                          │
  (4)   │   Google's own login page, then the consent screen       │
        │   "This app wants to view and edit events on your        │
        │    calendars."         [ Allow ]  [ Deny ]               │
        │◄────────────────────────────────────────────────────────►│
        │          you click Allow                                 │
        │                                                          │
  (5)   │  redirect to localhost:8000/api/google/oauth/callback/   │
        │     ?code=4/YOUR-ONE-TIME-CODE&state=xyz                        │
        │◄─────────────────────────────────────────────────────────┤
        ├─────────────────────────►│                              │
        │                          │                              │
        │                   (6) check `state` matches the one      │
        │                       we stored. If not → stop, 400.     │
        │                          │                              │
        │                   (7) POST oauth2.googleapis.com/token   │
        │                       code + client_id + CLIENT_SECRET   │
        │                          ├────────────────────────────► │
        │                          │   { access_token,            │
        │                          │     refresh_token,           │
        │                          │     expires_in: 3599 }       │
        │                          │◄──────────────────────────── │
        │                          │                              │
        │                   (8) encrypt both tokens, save to DB    │
        │                          │                              │
  (9)   │  redirect to localhost:5173/?google=connected            │
        │◄─────────────────────────┤                              │
```

---

## Why there is a code, and then a token

This is the part that confuses almost everyone the first time, so let us slow
down.

Why the two-step dance? Why does Google not just hand our app the access token in
step 5 and save everyone a request?

Because of **where step 5 travels**.

Step 5 is a browser redirect. The URL, including everything after the `?`, passes
through the browser. That means it can end up:

- in your browser history
- in the browser's address bar, visible on screen
- in server access logs
- in a `Referer` header sent to some other site
- in a screenshot or a shared link

That is a lot of places for a credential to leak into. So OAuth deliberately
sends something through the browser that is **almost useless on its own**: the
authorization code.

The code is useless alone because redeeming it in step 7 requires the **client
secret**, which only our server has. An attacker who steals the code from a log
file cannot do anything with it. They would also need our secret, and our secret
never travels through the browser — it only ever goes directly from our server to
Google's server over an encrypted connection.

On top of that, the code expires within minutes and can only be used once.

So the two-step dance exists to keep the valuable credential off the browser.
Once you see that, the design stops feeling bureaucratic and starts feeling
careful.

**This is also why a React app cannot do OAuth this way.** Step 7 needs the
client secret, and a React app cannot keep a secret. That is not a limitation of
React; it is a property of code that runs on someone else's computer. It is the
single clearest reason our backend exists.

---

## Access tokens and refresh tokens

Google's reply in step 7 contains two different tokens, and understanding the
difference between them is essential.

```
access_token    "ya29.YOUR-ACCESS-TOKEN"      lives about 1 hour
                Sent with every API call we make. If someone steals it,
                they can read and write the calendar — but only for an
                hour, and only the calendar, because that is all the
                scope allows.

refresh_token   "1//YOUR-REFRESH-TOKEN"        lives until revoked
                Never sent to the Calendar API. Only ever sent back to
                Google's token endpoint, to ask for a fresh access
                token. This is the valuable one. If someone steals
                this, they have lasting access.
```

Why have two at all? It is a trade-off between security and convenience.

If we only had long-lived tokens, then every API call would be carrying a
credential that is dangerous forever. A single leak — one log line, one error
report — would be permanent.

If we only had short-lived tokens, the user would have to click "Connect Google"
every hour, which nobody would tolerate.

So OAuth splits the two jobs. The token we use constantly is cheap to replace and
expires quickly. The token that can mint new ones is used rarely, sent to exactly
one URL, and kept locked away.

Think of the access token as cash in your pocket and the refresh token as your
bank card. You spend the cash freely; losing it costs you a little. You guard the
card, because it is the thing that produces more cash.

### Refreshing, in practice

Here is the logic we will write:

```
Before any call to the Calendar API:

    if the stored access token expires in less than 60 seconds:
        ask Google's token endpoint for a new one, using the refresh token
        save the new access token and its new expiry time
        keep the existing refresh token — Google usually does not send a new one

    make the API call with the (possibly new) access token
```

Two details that matter.

**Why 60 seconds of margin rather than checking for actual expiry?** Because
clocks drift, and because a request takes time. If the token expires in two
seconds and your request takes three, you fail for no good reason. Refreshing
slightly early costs nothing and removes a whole class of flaky failure.

**Why keep the old refresh token?** Because the refresh response normally
contains only a new access token. If you blindly overwrite your stored refresh
token with whatever came back, you will overwrite it with nothing, and your
integration will break the next time it needs to refresh. This is a classic bug
and now you will not write it.

### When refreshing fails

If the refresh request comes back with `invalid_grant`, the refresh token is dead.
Common causes: the user revoked access in their Google account settings, the
token sat unused for six months, or — the one you will actually hit — your OAuth
consent screen is in "Testing" mode, where Google expires refresh tokens after
seven days.

The right response is to mark the integration as disconnected and ask the user to
connect again. There is nothing else to try. Retrying in a loop just wastes
requests and may get you rate limited.

---

## Scopes, and why less is more

A scope is a string naming one specific permission. When we send the user to
Google, we list the scopes we want, and Google shows those to the user in plain
language on the consent screen.

For our app, we need to read upcoming events and create new ones. Google offers,
among others:

```
.../auth/calendar.events.readonly    read events only
.../auth/calendar.events             read and write events          ← we use this
.../auth/calendar.readonly           read events, calendar list, settings
.../auth/calendar                    full control, including sharing settings,
                                     calendar creation and deletion
```

We will ask for `https://www.googleapis.com/auth/calendar.events` and nothing
more. It is the smallest scope that covers both things we do.

Why does this matter when the broader scope would also work?

**Users are more likely to say yes.** A consent screen asking to "view and edit
events on your calendars" is reassuring. One asking to "see, edit, share and
permanently delete all the calendars you can access" makes people close the tab.

**Mistakes stay small.** If our code has a bug, or our token leaks, the damage is
bounded by what we asked for. We cannot accidentally delete somebody's calendar
if we never had permission to delete calendars.

**It documents intent.** Someone reading our code can see exactly what the app
can do, without reading the whole codebase.

This principle has a name — **least privilege** — and it applies far beyond
OAuth. Ask for the minimum, always.

---

## The `state` parameter and the attack it prevents

In step 2 we generate a random string, store it in the user's session, and send
it along to Google. In step 6 we compare what comes back against what we stored,
and reject the request if they differ.

This looks like pointless ceremony until you see what it stops.

Imagine `state` did not exist. Our callback accepts any `code` that arrives.

An attacker starts the OAuth flow themselves, using **their own** Google account.
They go as far as step 5 — they now have a valid authorization code tied to
*their* calendar — but they do not let it complete. Instead, they build a link:

```
http://localhost:8000/api/google/oauth/callback/?code=<attackers_code>
```

and get you to click it. Perhaps it is hidden in an image tag on a page you
visit, so you do not even have to click anything.

Your browser sends that request with your session cookie. Our backend, which has
no way to tell that it did not start this flow, happily exchanges the attacker's
code and stores the attacker's tokens against your session.

Now you are using our app, and it is connected to the attacker's calendar. Every
event you create goes into their calendar. Everything you think is private is
visible to them.

This is called **login CSRF**, or session fixation. The `state` parameter kills
it, because the attacker cannot guess the random value sitting in your session,
and without a matching value our callback refuses to proceed.

Three rules for `state`:

1. **Random and unguessable.** Use a cryptographically secure generator —
   `secrets.token_urlsafe(32)` in Python — not a timestamp, not a counter, not
   the user's ID.
2. **Stored on the server**, in the session. Not in a hidden form field, not in
   `localStorage`.
3. **Single use.** Delete it after a successful check, so the same callback cannot
   be replayed.

Both our integrations use this, which is why we write it once in
`integrations/oauth_state.py` and share it. Two copies of security code is how
one copy quietly drifts out of date.

---

## Slack's flow is the same shape

Here is the good news. When you reach document 05, you will find that Slack does
the same thing: send the user to an authorize URL, receive a code on a callback,
exchange the code plus your client secret for a token, store the token.

The differences are real but small:

- Slack installs into a **workspace** rather than a personal account, so what you
  get back is a **bot token** representing an app identity, plus the workspace's
  ID.
- Slack bot tokens **do not expire** by default, so there is no refresh step.
- Slack's errors come back in a different format, which trips people up — covered
  in document 05.

That is the payoff of learning the pattern rather than the provider. The second
OAuth integration you ever write takes a fraction of the time of the first, and
the tenth is almost mechanical.

---

## A summary you can keep

| Term | One-sentence meaning |
|---|---|
| **Resource owner** | The person who owns the data. You. |
| **Client** | The app asking for access. Ours. |
| **Authorization server** | The service that asks the user and issues tokens. Google's or Slack's login pages. |
| **Resource server** | The API holding the data. The Calendar API. |
| **Scope** | One named permission, shown to the user before they agree. |
| **Authorization code** | A short-lived, single-use ticket that travels through the browser and is useless without the client secret. |
| **Client ID** | Public name for our app. Fine to put in a URL. |
| **Client secret** | Proof that we are really that app. Backend only, forever. |
| **Access token** | Short-lived key sent with every API call. |
| **Refresh token** | Long-lived key used only to obtain new access tokens. |
| **`state`** | Random value proving the callback belongs to a flow we started. |
| **Redirect URI** | The exact address the provider is allowed to send users back to. |

---

## Official documentation

Get used to these pages. They are the real source of truth, and they are better
written than most tutorials.

- Google, OAuth 2.0 for web server applications:
  https://developers.google.com/identity/protocols/oauth2/web-server
- Google Calendar API reference:
  https://developers.google.com/calendar/api/v3/reference
- Slack, installing with OAuth:
  https://api.slack.com/authentication/oauth-v2
- Slack, scopes and permissions:
  https://api.slack.com/scopes

---

Next: [04 — The Google Calendar Flow](04-google-calendar-flow.md)
