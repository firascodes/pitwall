import type { AskEvent } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** POST /ask and call onEvent for each Server-Sent Event (EventSource cannot POST). */
export async function ask(
  question: string,
  threadId: string | null,
  onEvent: (e: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, thread_id: threadId }),
    signal,
  });
  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `The pit wall is offline (HTTP ${res.status}).`);
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
