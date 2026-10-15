// The only file that knows our backend's URLs. Components call these
// functions instead of using fetch() directly.

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8010";

export interface CalendarEvent {
  id: string;
  title: string;
  description: string;
  start: string;
  end: string;
  allDay: boolean;
  link: string;
  attendees: string[];
}

export interface Channel {
  id: string;
  name: string;
}

export interface Status {
  google: { connected: boolean };
  slack: { connected: boolean; team: string | null };
  // Whether the credentials are present in backend/.env at all.
  configured: { google: boolean; slack: boolean };
}

// Three outcomes, not two: the calendar event can succeed while the Slack
// message fails. TypeScript makes us handle all three.
export interface SlackResult {
  status: "sent" | "failed" | "skipped";
  error?: string;
}

export interface CreateEventResult {
  event: CalendarEvent;
  slack: SlackResult;
}

export interface NewEvent {
  title: string;
  description: string;
  start: string;
  end: string;
  attendees: string[];
  channelId: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/api${path}`, {
    credentials: "include", // carries the session cookie
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error ?? `Request failed (HTTP ${response.status})`);
  }
  return body as T;
}

export const api = {
  status: () => request<Status>("/status/"),
  events: () => request<CalendarEvent[]>("/events/"),
  channels: () => request<Channel[]>("/slack/channels/"),
  createEvent: (event: NewEvent) =>
    request<CreateEventResult>("/events/", {
      method: "POST",
      body: JSON.stringify(event),
    }),

  // OAuth needs a real browser navigation, not a fetch() call, because the
  // user has to see Google's and Slack's own pages.
  connect: (service: "google" | "slack") => {
    window.location.href = `${BASE}/api/${service}/auth/`;
  },
};
