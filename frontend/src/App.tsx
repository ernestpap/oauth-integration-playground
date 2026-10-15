import { useEffect, useState } from "react";
import {
  api,
  type CalendarEvent,
  type Channel,
  type Status,
} from "./api";

type Message = { kind: "success" | "warning" | "error"; text: string };

const emptyForm = {
  title: "",
  description: "",
  start: "",
  end: "",
  attendees: "",
  channelId: "",
};

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState<Message | null>(null);
  const [saving, setSaving] = useState(false);

  // On load, show whatever the OAuth callback redirected back with, then
  // tidy the query string so a refresh does not repeat the message.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const error = params.get("error");
    if (connected) setMessage({ kind: "success", text: `${connected} connected.` });
    if (error) setMessage({ kind: "error", text: error });
    if (connected || error) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    void load();
  }, []);

  async function load() {
    try {
      const next = await api.status();
      setStatus(next);
      setEvents(next.google.connected ? await api.events() : []);
      setChannels(next.slack.connected ? await api.channels() : []);
    } catch (error) {
      setMessage({ kind: "error", text: describe(error) });
    }
  }

  async function submit(submitEvent: React.FormEvent) {
    submitEvent.preventDefault();
    setMessage(null);

    // Quick checks here are a courtesy - the backend checks again, because
    // anyone can skip this form and call the API directly.
    if (!form.title.trim()) {
      return setMessage({ kind: "error", text: "Please give the event a title." });
    }
    if (!form.start || !form.end) {
      return setMessage({ kind: "error", text: "Please set a start and end time." });
    }
    if (form.end <= form.start) {
      return setMessage({
        kind: "error",
        text: "The end time must be after the start time.",
      });
    }

    setSaving(true);
    try {
      const result = await api.createEvent({
        title: form.title,
        description: form.description,
        start: form.start,
        end: form.end,
        attendees: form.attendees
          .split(",")
          .map((email) => email.trim())
          .filter(Boolean),
        channelId: form.channelId,
      });

      // All three outcomes get their own message. Reporting a failed Slack
      // post as success would tell the user their team was notified when
      // nobody was.
      if (result.slack.status === "sent") {
        setMessage({ kind: "success", text: "Event created and posted to Slack." });
      } else if (result.slack.status === "failed") {
        setMessage({
          kind: "warning",
          text: `Event created, but the Slack message failed: ${result.slack.error}`,
        });
      } else {
        setMessage({ kind: "success", text: "Event created." });
      }

      setForm({ ...emptyForm, channelId: form.channelId });
      setEvents(await api.events());
    } catch (error) {
      setMessage({ kind: "error", text: describe(error) });
    } finally {
      setSaving(false);
    }
  }

  const googleReady = status?.google.connected ?? false;

  return (
    <main>
      <h1>Calendar &rarr; Slack</h1>
      <p className="lead">
        Create a Google Calendar event and announce it in Slack.
      </p>

      {message && <div className={`message ${message.kind}`}>{message.text}</div>}

      <section className="card">
        <h2>Connections</h2>
        <div className="row">
          <Connection
            name="Google Calendar"
            connected={googleReady}
            detail={null}
            configured={status?.configured.google ?? false}
            onConnect={() => api.connect("google")}
          />
          <Connection
            name="Slack"
            connected={status?.slack.connected ?? false}
            detail={status?.slack.team ?? null}
            configured={status?.configured.slack ?? false}
            onConnect={() => api.connect("slack")}
          />
        </div>
      </section>

      <section className="card">
        <h2>New event</h2>
        {!googleReady ? (
          <p className="muted">Connect Google Calendar to create events.</p>
        ) : (
          <form onSubmit={submit}>
            <label>
              Title
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Design review"
              />
            </label>

            <label>
              Description
              <textarea
                rows={2}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="What is this meeting about?"
              />
            </label>

            <div className="row">
              <label>
                Starts
                <input
                  type="datetime-local"
                  value={form.start}
                  onChange={(e) => setForm({ ...form, start: e.target.value })}
                />
              </label>
              <label>
                Ends
                <input
                  type="datetime-local"
                  value={form.end}
                  onChange={(e) => setForm({ ...form, end: e.target.value })}
                />
              </label>
            </div>

            <label>
              Attendees
              <input
                value={form.attendees}
                onChange={(e) => setForm({ ...form, attendees: e.target.value })}
                placeholder="someone@example.com, someone-else@example.com"
              />
              <small>Comma separated. They will receive an email invitation.</small>
            </label>

            <label>
              Announce in Slack
              <select
                value={form.channelId}
                onChange={(e) => setForm({ ...form, channelId: e.target.value })}
                disabled={channels.length === 0}
              >
                <option value="">
                  {status?.slack.connected
                    ? "Do not post to Slack"
                    : "Slack is not connected"}
                </option>
                {channels.map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    #{channel.name}
                  </option>
                ))}
              </select>
            </label>

            {/* Disabled while saving so an impatient double-click cannot
                create the event twice. */}
            <button type="submit" disabled={saving}>
              {saving ? "Creating…" : "Create event"}
            </button>
          </form>
        )}
      </section>

      <section className="card">
        <h2>Upcoming events</h2>
        {!googleReady ? (
          <p className="muted">Connect Google Calendar to see your events.</p>
        ) : events.length === 0 ? (
          <p className="muted">Nothing coming up.</p>
        ) : (
          <ul className="events">
            {events.map((event) => (
              <li key={event.id}>
                <strong>{event.title}</strong>
                <span className="when">{formatWhen(event)}</span>
                {event.attendees.length > 0 && (
                  <span className="muted">
                    {event.attendees.length} attendee
                    {event.attendees.length === 1 ? "" : "s"}
                  </span>
                )}
                {event.link && (
                  <a href={event.link} target="_blank" rel="noreferrer">
                    Open
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function Connection({
  name,
  connected,
  detail,
  configured,
  onConnect,
}: {
  name: string;
  connected: boolean;
  detail: string | null;
  configured: boolean;
  onConnect: () => void;
}) {
  return (
    <div className="connection">
      <div>
        <span className={connected ? "dot on" : "dot off"} />
        <strong>{name}</strong>
        <div className="muted">
          {connected ? (detail ?? "Connected") : "Not connected"}
        </div>
      </div>
      {!connected &&
        (configured ? (
          <button type="button" onClick={onConnect}>
            Connect
          </button>
        ) : (
          <small className="muted">Add credentials to backend/.env</small>
        ))}
    </div>
  );
}

function formatWhen(event: CalendarEvent) {
  const [date, time] = event.start.split("T");
  if (event.allDay || !time) return `${date} (all day)`;
  return `${date} at ${time.slice(0, 5)}`;
}

function describe(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}
