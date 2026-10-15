# Start Here

> **Note:** these documents were written as the plan, before the code existed.
> The MVP that got built is simpler than what they describe — one Django app
> instead of three, no encryption layer, no test suite, and slightly different
> endpoint paths (`/api/google/callback/` rather than
> `/api/google/oauth/callback/`). The backend also runs on port **8010**, not
> 8000, because another service on this machine owns 8000.
>
> So: read these for the **concepts**, which all still apply, and treat the
> [README](../README.md) as the source of truth for paths, ports and commands.

Welcome. These documents explain the project we are about to build together, in
plain English, before we write a single line of code.

I wrote them in a specific order. Each one assumes you have read the ones before
it. If you read them top to bottom, every new term will have been explained
earlier.

You do not need to memorise any of this. The goal is that when we start writing
code, nothing feels like magic. You should be able to look at any file we create
and say "I know why this exists and what problem it solves."

---

## The reading order

| # | Document | What it covers | Read when |
|---|---|---|---|
| 01 | [What We Are Building](01-what-we-are-building.md) | The app, and the list of real skills you will pick up | First |
| 02 | [Architecture](02-architecture.md) | The pieces of the system and how they talk to each other | Second |
| 03 | [OAuth Explained Simply](03-oauth-explained.md) | What OAuth is and why it exists at all | Before anything about Google or Slack |
| 04 | [The Google Calendar Flow](04-google-calendar-flow.md) | Google login, tokens, refreshing, reading and creating events | Before Phase 2 |
| 05 | [The Slack Flow](05-slack-flow.md) | Slack apps, bot tokens, channels, sending messages | Before Phase 3 |
| 06 | [Connecting Both Integrations](06-connecting-both.md) | What happens when one button press has to touch two companies | Before Phase 4 |
| 07 | [Folder Structure](07-folder-structure.md) | Every folder and file, and why it is where it is | Before Phase 1 |
| 08 | [Accounts and Setup](08-prerequisites-setup.md) | Click-by-click setup of Google Cloud and Slack | Before Phase 2 |
| 09 | [Implementation Plan](09-implementation-plan.md) | The six phases, with a checklist for each | To see the road ahead |
| 10 | [Security Notes](10-security-notes.md) | What we do safely, and which shortcuts must change before production | Any time, but definitely by the end |
| 11 | [Glossary](11-glossary.md) | Every piece of jargon, defined in one sentence | Whenever a word confuses you |
| 12 | [Troubleshooting](12-troubleshooting.md) | The errors you will hit, and what each one actually means | When something breaks |

---

## If you only have ten minutes

Read **01** and **03**. Those two carry most of the understanding. Everything
else is detail you can look up when you reach it.

---

## How to read the diagrams

All the diagrams in these documents are drawn with plain text characters so they
work anywhere, including inside your terminal.

Arrows show the direction a request travels:

```
  Browser  ──────────►  Backend      the browser is asking the backend for something
  Browser  ◄──────────  Backend      the backend is answering
```

When you see a numbered step like `(3)`, it matches a numbered explanation
underneath the diagram. Read the diagram once to get the shape, then read the
numbered notes to understand each step.

---

## A note on how we will work

I am going to build this with you one phase at a time. At the end of each phase
there is a checklist. I will stop there and wait for you to confirm that it
actually works on your machine before we move on.

That pause matters more than it sounds. Integration bugs compound. If your token
storage is subtly wrong in Phase 2, you will spend Phase 4 debugging Slack code
that was never broken. Confirming each phase keeps the number of possible
explanations for any bug small.

Two more things worth saying up front:

**Please interrupt me.** If an explanation does not land, say so. "I do not
understand why the state parameter is needed" is a genuinely useful message, and
re-explaining it differently is part of the job, not an interruption to it.

**When something breaks, we diagnose before we rewrite.** The instinct when code
fails is to replace it with different code and hope. That teaches you nothing and
usually moves the bug rather than fixing it. We will read the error, form a guess
about the cause, and check that guess. Debugging is the skill that transfers to
every project you ever work on. The code we write here is not.
