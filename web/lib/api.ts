import type { AskEvent } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** An API refusal; `code` is set for quota limits so the UI can offer sign-in. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly code?: "guest_limit" | "user_limit",
  ) {
    super(message);
  }
}

const bearer = (token?: string): Record<string, string> => (token ? { authorization: `Bearer ${token}` } : {});

/** POST /ask and call onEvent for each Server-Sent Event (EventSource cannot POST). */
export async function ask(
  question: string,
  threadId: string | null,
  onEvent: (e: AskEvent) => void,
  token?: string,
): Promise<void> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json", ...bearer(token) },
    body: JSON.stringify({ question, thread_id: threadId }),
  });
  if (!res.ok || !res.body) {
    const detail = (await res.json().catch(() => null))?.detail;
    if (detail?.code) throw new ApiError(detail.message, detail.code);
    throw new ApiError(typeof detail === "string" ? detail : `The pit wall is offline (HTTP ${res.status}).`);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = chunk.match(/^event: (.+)$/m)?.[1];
      const data = chunk.match(/^data: (.+)$/m)?.[1];
      if (event && data) onEvent({ event, data: JSON.parse(data) } as AskEvent);
    }
  }
}

export type LapTelemetry = {
  lap_id: string;
  distance_m: number[];
  time_s: number[];
  x_m: number[];
  y_m: number[];
  speed_kph: number[];
};

const laps = new Map<string, Promise<LapTelemetry>>();

export function getLap(lapId: string): Promise<LapTelemetry> {
  if (!laps.has(lapId)) {
    const request = fetch(`${API_URL}/laps/${lapId}`).then((r) => {
      if (!r.ok) throw new Error(`no telemetry for ${lapId}`);
      return r.json();
    });
    request.catch(() => laps.delete(lapId));
    laps.set(lapId, request);
  }
  return laps.get(lapId)!;
}

export type DemoUsage = { day: string; spent_usd: number; cap_usd: number };

export async function getDemoUsage(): Promise<DemoUsage | null> {
  return fetch(`${API_URL}/usage`)
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
}

/** Free hosts sleep: ping on page load so the server is awake by the first question. */
export async function wake(): Promise<boolean> {
  return fetch(`${API_URL}/health`)
    .then((r) => r.ok)
    .catch(() => false);
}

export type Quota = { auth: boolean; signed_in: boolean; used: number; limit: number };

export async function getQuota(token?: string): Promise<Quota | null> {
  return fetch(`${API_URL}/quota`, { headers: bearer(token) })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
}
