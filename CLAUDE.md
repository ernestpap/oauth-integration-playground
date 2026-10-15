# CLAUDE.md

## How to talk to me

I am a junior developer. I want to understand things, not just copy code.

Write in plain, simple English. Always. Follow these rules:

**Short sentences.** One idea per sentence. If a sentence has three commas in it,
split it into three sentences.

**Explain every new word the first time you use it.** Do not write "idempotent"
or "CSRF" or "cursor pagination" and move on. Say what it means in normal words
first.

**Do not pack information tightly.** It is better to say something in four easy
sentences than in one clever sentence. Repeating an idea is fine. I would rather
read more words and understand them.

**Use simple words.** Say "use" not "utilise". Say "so" not "consequently". Say
"but" not "nevertheless".

**Avoid long dashes and brackets inside sentences.** They hide extra ideas inside
a sentence I am already reading. Start a new sentence instead.

**Use numbered steps for anything I have to do.** Tell me what to type. Then tell
me what should happen. Then tell me what it means.

**Keep tables small.** Two or three columns. Use tables for lists of facts, not
for explanations. Explanations go in sentences.

**Tell me why, not just what.** If you say "add this line", also say what breaks
without it.

**Say when something is a real risk.** If a command deletes things or sends
things to the internet, say so plainly before I run it.

---

## What this project is

A small web app. It connects Google Calendar and Slack.

You connect your Google account. You connect your Slack workspace. You see your
next calendar events. You fill in a form to create a new event. When the event is
created, the app posts a message about it in a Slack channel you chose.

It is a learning project. The goal is to understand how real apps connect to
other companies' services.

## How to run it

The app is two programs. You need both running at the same time, in two separate
terminals.

```powershell
# Terminal 1 - the backend (Django)
cd backend
.\venv\Scripts\activate
python manage.py runserver 8010

# Terminal 2 - the frontend (React)
cd frontend
npm run dev
```

Then open <http://localhost:5173> in your browser.

## Important things to remember

**Open port 5173, not 8010.** The page you look at is on 5173. The backend on
8010 has no page to look at. It only sends data. If you open 8010 in a browser
you get a 404 error, and that is normal.

**The backend uses port 8010, not 8000.** Django normally uses 8000. Another
program on this computer already uses 8000. So you must type the port:
`python manage.py runserver 8010`.

**Restart Django after you change `.env`.** Django only reads that file when it
starts. If you change a value and nothing happens, this is why.

**The port number appears in four places.** They must all match:
`backend/.env`, `frontend/src/api.ts`, `backend/config/settings.py`, and the
redirect URLs you register with Google and Slack.

## Where the code is

```
backend/config/settings.py   all configuration, reads the .env file
backend/core/models.py       the two database tables
backend/core/google.py       all Google Calendar code
backend/core/slack.py        all Slack code
backend/core/views.py        the web addresses (endpoints)
backend/core/errors.py       error handling
frontend/src/api.ts          calls the backend
frontend/src/App.tsx         the whole page
docs/                        long explanations of how it all works
```

## Current state

The app is built and works. Google and Slack credentials are not added yet. Both
Connect buttons say "Add credentials to backend/.env" until you add them. The
README explains how to get those credentials.

Secrets live in `backend/.env`. Git ignores that file. Never put secrets in the
frontend folder.
