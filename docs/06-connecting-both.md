# 06 — Connecting Both Integrations

This is the most interesting document in the set, and the one most worth reading
slowly. Everything up to now has been "how do I talk to this service." This is
"what do I do when two services have to cooperate and one of them lets me down."

Read this before Phase 4.

---

## The problem, stated plainly

The user presses one button: **Create Event**.

Behind that button, two separate companies have to do something:

1. Google has to create the calendar event and email the attendees.
2. Slack has to post an announcement in a channel.

Now, a question that sounds simple and is not:

> What should happen if Google succeeds and Slack fails?

Have a think before reading on. Your instinct is probably one of these:

- *"Return an error, obviously. Something went wrong."*
- *"Return success. The event was created, which is what the user wanted."*
- *"Undo the event so the system is consistent."*

All three are defensible, and all three are wrong in a way worth understanding.

---

## Why you cannot just undo it

In a database, this problem has a clean solution called a **transaction**. You
begin, you make several changes, and if any one fails you roll back. Either
everything happened or nothing did. The database guarantees it.

You might reasonably hope for the same thing here. There is no such thing.

Google and Slack are different companies, on different servers, with no shared
transaction and no knowledge of each other. There is no "begin transaction"
spanning both. You make one request, then you make another, and in between
anything can happen.

"Just delete the event if Slack fails" fails for a deeper reason than being
awkward to code: **the event was never only in the database.** By the time Google
returned success, it had already:

- appeared on your calendar, and possibly on your phone's lock screen
- sent invitation emails to real attendees
- shown up in the calendars of everyone who accepted

You cannot un-send an email. Deleting the event now produces a *second* round of
notifications — cancellation emails to everyone — because of a failure in a Slack
message they never knew was supposed to exist. You have made things worse in the
name of consistency.

This is the central lesson of the phase: **once an action has escaped into the
real world, it is not reversible.** It can only be compensated for, which is a
different and messier thing. So you order your operations to make the
irreversible step as late and as certain as possible, and you report honestly
about what followed it.

---

## The answer: three outcomes, not two

The mistake buried in the question is the assumption that there are two possible
results. There are three, and we are going to represent all three.

```
Outcome A    Google created the event. Slack posted the message.
             → Everything worked.

Outcome B    Google created the event. Slack failed.
             → The user got what they primarily wanted. The announcement
               did not happen. Both facts need saying.

Outcome C    Google failed. We never attempted Slack.
             → Nothing happened. There is nothing to announce.
```

Outcome B is the one that matters. If you collapse it into A, your app lies to
the user — they believe their team was notified when nobody was. If you collapse
it into C, your app also lies — the user thinks nothing happened, tries again,
and now has two events in their calendar and two sets of invitation emails.

Both collapses cause real damage. The only honest answer is to report outcome B
as what it is: **partial success, described precisely.**

In HTTP terms:

```
Outcome A    201 Created
             { "event": {...}, "slack": { "status": "sent", "channel": "#demo" } }

Outcome B    201 Created
             { "event": {...}, "slack": { "status": "failed",
                                          "error": "missing_scope",
                                          "hint": "Reinstall the Slack app
                                                   to grant permission" } }

Outcome C    502 Bad Gateway
             { "error": "Could not create the calendar event",
               "detail": "Google returned 403 insufficientPermissions" }
```

Outcome B returns **201, not 500**. That choice sometimes surprises people, so
here is the reasoning: the status code answers "did the thing the user asked for
happen?" and it did. The event exists. Returning 500 would tell the frontend to
show a red error, the user would assume nothing happened, and they would try
again — creating a duplicate event. The status code describes the primary
outcome; the `slack` object carries the nuance.

The frontend then renders outcome B as an amber warning rather than a green
success or a red failure:

> **Event created.** The Slack notification could not be sent: the app is missing
> the `chat:write` permission. Reinstall the Slack app to fix this.

Clear, honest, and actionable. The user knows the event is real, knows their team
was not told, and knows what to do about it.

---

## The order of operations, and why

Here is the full sequence we will implement.

```
POST /api/calendar/events/
   {
     "title": "Design review",
     "description": "Walk through the new onboarding flow",
     "start": "2026-10-20T15:00:00+05:30",
     "end":   "2026-10-20T16:00:00+05:30",
     "attendees": ["teammate@example.com"],
     "slack_channel_id": "C04IJKLMNOP"
   }

   │
   ├─ (1) VALIDATE EVERYTHING LOCALLY
   │        Is the end time after the start time?
   │        Are the email addresses well formed?
   │        Is the title present and not absurdly long?
   │        Is the channel ID one that exists?
   │
   │        If anything is wrong → 400 Bad Request, stop here.
   │        Nothing has happened anywhere in the world.
   │
   ├─ (2) CHECK THE INTEGRATIONS ARE CONNECTED
   │        Is there a Google credential? If not → 409, "connect Google first".
   │        Refresh the Google access token if it expires soon.
   │
   │        Still nothing irreversible has happened.
   │
   ├─ (3) CREATE THE GOOGLE EVENT          ← the irreversible step
   │        If this fails → 502, stop. No Slack message is attempted.
   │        If it succeeds → we now hold google_event_id, which we need next.
   │
   ├─ (4) CLAIM THE NOTIFICATION
   │        EventNotification.objects.get_or_create(
   │            google_event_id=..., channel_id=...)
   │
   │        If a row already existed → somebody already sent this. Skip Slack
   │        entirely and return the existing status.
   │
   ├─ (5) POST TO SLACK
   │        Success → mark the row "sent".
   │        Failure → mark the row "failed" and record the error string.
   │        Either way, we do not raise. A Slack failure is data, not a crash.
   │
   └─ (6) RESPOND, describing both halves accurately.
```

### Why validate first

Validation is cheap, local, and instant. Doing it before any network call means
that the overwhelmingly common failure — a typo in the form — costs nothing and
changes nothing anywhere.

There is a general principle here worth internalising: **do your cheap, reversible
checks before your expensive, irreversible actions.** Front-load everything that
can say no.

### Why Google before Slack

Two reasons.

**The dependency.** The Slack message should contain a link to the event, and the
link comes from Google's response. We literally cannot compose a good message
before the event exists.

**The logic.** The Slack message is an *announcement*. Announcements follow
facts. Posting "Design review has been scheduled" before the event is scheduled
means that if Google then fails, you have told the whole team about a meeting
that does not exist. That is worse than silence.

So: do the thing, then announce the thing. In that order, the worst case is an
event nobody was told about, which is recoverable by telling them. The other
order gives you a phantom meeting, which is not.

---

## Idempotency: not sending the message twice

**Idempotent** means doing something twice has the same effect as doing it once.

Here is the scenario it protects against. The user clicks Create Event. The
request takes two seconds, because Google and Slack are both being slow. Nothing
visibly happens. So they click again.

Without protection, you now have two requests in flight, and you get two calendar
events and two Slack messages. The user, who pressed a button twice, has
double-booked their team and spammed a channel.

### The naive fix, and why it is not enough

The obvious answer is to disable the button while the request is in flight, and
we will absolutely do that in Phase 5 — it is good UX.

But it is not a solution, for a reason that generalises well beyond this project:
**the frontend cannot enforce anything.** The user can refresh mid-request, open
two tabs, have a flaky connection that silently retries, or bypass the UI
entirely with `curl`. A disabled button improves the common case; it does not make
the system correct.

Correctness has to live on the backend.

### The real fix: let the database enforce it

We create a table whose job is to record "this event has been announced in this
channel":

```
EventNotification
    google_event_id    "a1b2c3d4e5f6g7h8i9j0k1l2m3"
    channel_id         "C04IJKLMNOP"
    status             "sent" | "failed"
    error              "missing_scope"  (null when sent)
    created_at         2026-10-14 10:32:14

    UNIQUE (google_event_id, channel_id)     ← this line does the work
```

That unique constraint is the whole mechanism. It tells the database: there may
never be two rows with the same event and channel.

Then, before posting to Slack, we **claim** the notification:

```python
notification, created = EventNotification.objects.get_or_create(
    google_event_id=event_id,
    channel_id=channel_id,
)

if not created:
    # Someone already did this. Do not post again.
    return notification

# We are the first. Our job to send it.
send_slack_message(...)
```

### Why a database constraint rather than a check in Python

You might wonder why we do not simply write:

```python
if EventNotification.objects.filter(...).exists():
    return          # already sent
else:
    send_slack_message(...)
```

Because of what can happen between those two lines.

Two requests arrive at nearly the same instant. Request A checks: no row exists.
Request B checks: no row exists. Request A sends the message. Request B sends the
message. Both checks were correct at the moment they ran, and two messages went
out anyway.

This is a **race condition**, and the gap between "check" and "act" is where a
whole category of real-world bugs lives. They are miserable to reproduce, because
they only appear under timing you cannot easily recreate, which is why they tend
to be found in production rather than in testing.

A unique constraint closes the gap. The database performs the check and the
insert as one indivisible operation. If two requests race, exactly one wins the
insert and the other gets told the row already exists. The database is the only
component that can make that guarantee, because it is the only one with a single
authoritative view of the data.

The lesson to carry forward: **when correctness depends on "only one of these may
exist," say so in the schema.** Do not express it as application logic and hope
the timing is kind.

### A bonus from this table

We built `EventNotification` for deduplication, but it turns out to be useful for
two more things, which is often a sign of a good design.

It is an **audit log**. "Did we notify about this event?" becomes a query rather
than a search through log files.

It is a **retry queue waiting to happen**. Every row with `status="failed"` is a
message that should have been sent and was not. In a production system a
background job would select those rows every few minutes and retry them, which is
how you convert outcome B into eventual outcome A without troubling the user.

We are not building that job — it needs Celery and a message broker, and that is a
separate topic. But the data model is already shaped for it, so I will show you
exactly which function the job would call. Designing so the next step is easy,
without building the next step prematurely, is a real skill.

---

## Where the two integrations touch

The entire coupling between the Google half and the Slack half is one function
call. In `slack_app/notifications.py`:

```python
def notify_event_created(event, channel_id):
    """
    Announce a newly created calendar event in a Slack channel.

    Returns an EventNotification describing what happened. Never raises
    for a Slack-side failure: the caller has already created the calendar
    event, and a failed announcement must not turn a real success into
    an error response.
    """
```

That docstring is doing real work. It states the contract — specifically, that
this function does not raise on Slack failures — which is exactly the thing a
future reader would otherwise get wrong.

And in `google_calendar/views.py`:

```python
event = google_client.create_event(...)          # the irreversible step

notification = None
if channel_id:
    notification = notify_event_created(event, channel_id)

return Response(build_response(event, notification), status=201)
```

That is the whole integration between the two halves. Five lines.

It is worth stopping to appreciate why it is only five lines. It is not because
the problem was easy. It is because we spent Phases 2 and 3 making each side
self-contained, with its own models, its own client, its own error handling. The
work of keeping things separate earlier is what makes joining them trivial now.

When people say software should be "modular," this is the payoff they mean — not
an abstract notion of tidiness, but that the change you make later is small.

---

## What we are deliberately not doing

Three things a production version would add. Each is a reasonable next step and
each is out of scope on purpose.

**Automatic retries.** Covered above. Needs a task queue.

**Sending the Slack message in the background.** Right now the user waits for
Slack before they get their response. If Slack were slow, event creation would
feel slow — even though the event was created in the first few hundred
milliseconds. A production app would return as soon as Google succeeded and hand
the notification to a worker.

We are keeping it synchronous because the sequence is visible this way. You can
watch the requests happen in order in your terminal, which is worth more while
learning than the performance is.

**A circuit breaker.** If Slack is down, every request pointlessly waits for a
timeout. A circuit breaker notices repeated failures and stops trying for a
while, failing fast instead. Useful at scale, unnecessary here.

---

## What to take away from this document

Four ideas, in order of how often they will matter in your career:

1. **There is no transaction across two companies.** Every multi-service action
   has a window in which it can be half-done. Design for that window rather than
   pretending it does not exist.

2. **Order your steps so the irreversible one is last and best-informed.** Cheap
   checks first. Things that send emails to real people as late as possible.

3. **Partial success is a real outcome and deserves a real representation.**
   Squashing it into either neighbour means lying to your user, and the lie is
   what makes integrations feel untrustworthy.

4. **Put uniqueness rules in the database.** Application-level checks have a gap
   between looking and acting, and under concurrency that gap is where the bug
   lives.

---

Next: [07 — Folder Structure](07-folder-structure.md)
