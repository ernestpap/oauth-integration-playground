# 01 — What We Are Building

## The app, described as a user would experience it

You open a page in your browser. It shows two buttons: **Connect Google** and
**Connect Slack**.

You click Connect Google. The browser sends you to a real Google page, the kind
you have seen a hundred times, which says something like "This app wants to view
and edit events on your calendar" with Allow and Deny buttons. You click Allow.
Google sends you back to our app, which now says **Google: connected**.

You click Connect Slack. Same idea: a real Slack page asks whether you want to
install this app into your workspace, and lists exactly what it will be able to
do. You approve. Back on our page: **Slack: connected**.

Now the page shows your next ten upcoming calendar events, pulled live from your
actual Google Calendar.

Below that is a form. You type a title, a description, a start time, an end time,
and the email addresses of a couple of attendees. You pick a Slack channel from a
dropdown, say `#demo-notifications`. You click **Create Event**.

Three things happen:

1. The event appears in your real Google Calendar.
2. Your attendees get a real email invitation.
3. A message appears in that Slack channel announcing the new event.

The page tells you it worked. If something went wrong, it tells you what went
wrong and why, in words that actually help.

That is the whole app.

---

## Why something this small is worth building

It looks tiny. A form and a couple of buttons. But to make those few interactions
work correctly, you have to solve nearly every problem that makes integration
work hard in real jobs.

Here is what I mean. The moment you want to touch somebody else's Google
Calendar, you immediately face these questions:

- How do you get permission to read a stranger's calendar without asking for
  their password?
- Where do you put the credential you receive, given that your database might
  one day be stolen?
- That credential expires in an hour. What happens to your app at minute 61?
- What if the user changes their mind and revokes your access?
- What if Google is slow, or down, or returns an error you have never seen
  before?

And then Slack adds its own questions:

- What is the difference between an app that acts as *you* and an app that acts
  as *itself*?
- What happens when you ask Slack to post to a channel your bot was never
  invited to?
- What do you do when Slack says "you are sending messages too fast, wait"?

And finally, the question that only appears once you combine them, which is the
most interesting one in the project:

- The event was created in Google, but the Slack message failed. Was that a
  success or a failure?

There is no clean answer to that last one, which is exactly why it is worth
thinking about carefully. We come back to it in document 06.

---

## The specific things you will learn

I want to be concrete about this, because "you will learn about integrations" is
not a useful promise. Here is the actual list.

### Authorization and identity

You will learn **what OAuth 2.0 actually is** — not as a buzzword, but as a
sequence of HTTP requests you could draw from memory. You will understand why it
has the shape it does, which means you will be able to work with any OAuth
provider afterwards, not just these two. Google and Slack are the two examples
here, but Stripe, GitHub, Microsoft, Zoom and Shopify all use the same pattern.

You will learn **the difference between an access token and a refresh token**,
why both exist, and what goes wrong if you confuse them.

You will learn **what scopes are**, and why asking for fewer of them is a feature
rather than a limitation.

You will learn **why a redirect needs a `state` parameter**, by understanding the
specific attack that happens when it is missing. This is a genuine security
concept, and once you have seen it you will start noticing its absence in other
people's code.

### Handling credentials responsibly

You will learn **why secrets live in environment variables** rather than in your
source code, and what "do not commit your `.env` file" is actually protecting you
from.

You will learn **why the frontend can never hold a secret**. Not "should not" —
*cannot*. Anything your React app knows, your users know, because they can read
it in their browser.

You will learn **how to encrypt sensitive values before storing them** in a
database and, just as importantly, what that does and does not protect against.

### Talking to APIs you do not control

You will learn to **read API documentation** and turn it into working code. We
will use Google's and Slack's official docs as the source of truth throughout,
rather than me simply telling you what the APIs do. That habit is the difference
between a developer who can integrate anything and one who can only integrate
things somebody has already written a tutorial for.

You will learn that **errors from third parties are a normal part of the control
flow**, not rare exceptional events. You will handle expired tokens, revoked
access, missing permissions, bad input and rate limits deliberately, because a
real integration spends a meaningful fraction of its life in one of those states.

You will learn about **rate limiting**: what it is, why providers do it, and why
the correct response is to wait exactly as long as they tell you to.

### Designing for failure

You will learn about **partial failure**: what to do when a single user action
requires two separate systems to cooperate and only one of them does its job.

You will learn about **idempotency**, which is the property that doing something
twice has the same effect as doing it once. You will implement it so that an
impatient double-click does not post two Slack messages.

You will learn **where validation belongs**, and why the answer is "both sides,
for different reasons."

### Ordinary professional habits

You will learn what belongs in the **frontend** versus the **backend**, as a
principle rather than as a convention you follow because somebody said so.

You will learn to **test each piece before building the next one**, using `curl`
against your own API before any user interface exists at all.

You will learn to **write tests for integration logic without calling the real
APIs**, by faking their responses. This is how you test the "what if Google
returns an error" path, since you cannot ask Google to fail on demand.

---

## What we are deliberately not building

Keeping scope small is a skill too, so it is worth naming what is out of scope.

**No user accounts or login.** The app assumes one person is using it. This keeps
the focus on integration rather than on authentication scaffolding, which is a
whole separate topic. I will point out exactly which lines of code would change
in order to support many users, so you know where the seam is.

**No background job system.** When a Slack message fails, we record the failure
but we do not automatically retry it later. Retrying properly needs a task queue
such as Celery, and that is a large topic in its own right. I will show you
precisely where it would plug in.

**No deployment.** This runs on your machine. Document 10 covers what would have
to change before this could go on the public internet, which is worth
understanding even while you are not doing it.

**No Docker, no Kubernetes, no microservices.** This is one backend and one
frontend. Extra infrastructure here would teach you infrastructure, not
integration.

**Nothing clever.** Where there is a choice between a short, surprising solution
and a longer, obvious one, we will take the obvious one. Code that reads plainly
is easier to learn from, and frankly easier to maintain.

---

## The one idea to carry through the whole project

If you forget everything else, keep this:

> **Your backend is the only part of the system that holds credentials.**

The React app in the browser never sees a client secret, never sees a refresh
token, never sees a Slack bot token. It only ever talks to your own backend, and
your backend is the only thing that talks to Google and Slack.

Almost every security mistake in integration work is a violation of that one
sentence. Keep it in mind and you will avoid most of them without having to
memorise a list of rules.

---

Next: [02 — Architecture](02-architecture.md)
