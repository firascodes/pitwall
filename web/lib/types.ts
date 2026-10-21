export type Query = { cypher: string; params: Record<string, unknown>; rows: number; ms: number };

export type ToolCall = {
  id: string;
  name: string;
  args: Record<string, unknown>;
  step: number;
  ok?: boolean;
  preview?: string;
  queries?: Query[];
};

export type Usage = {
  llm_calls: number;
  input_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  usd: number;
};

export type Lap = { lap_id: string; driver: string; time: string };

export type CornerRow = {
  corner: string;
  distance_m: number;
  a_gain_s: number;
  a_min_kph: number;
  b_min_kph: number;
  a_brake_m: number | null;
  b_brake_m: number | null;
  cause: string;
};

export type ReplayData = { laps: string[]; drivers: string[]; times: string[]; ghost: boolean };
export type DeltaData = { distance_m: number[]; b_behind_a_s: number[]; a: Lap; b: Lap };
export type CornerData = { rows: CornerRow[]; a: Lap; b: Lap };
export type Row = Record<string, unknown>;

export type Block =
  | { type: "text"; text: string }
  | { type: "chips"; options: string[] }
  | { type: "lap_replay"; title: string; source: string; data: ReplayData }
  | { type: "delta_chart"; title: string; source: string; data: DeltaData }
  | { type: "corner_table"; title: string; source: string; data: CornerData }
  | { type: "results_table" | "h2h_card"; title: string; source: string; data: { rows: Row[] } }
  | { type: "stint_timeline"; title: string; source: string; data: { stints: Row[] } };

export type Turn = {
  id: string;
  question: string;
  tools: ToolCall[];
  blocks: Block[];
  usage?: Usage;
  error?: string;
  startedAt: number;
  endedAt?: number;
};

export type Thread = { id: string | null; title: string; turns: Turn[]; updatedAt: number };

export type AskEvent =
  | { event: "start"; data: { thread_id: string } }
  | {
      event: "step";
      data: { node: string; tool_calls: { id: string; name: string; args: Record<string, unknown> }[] };
    }
  | {
      event: "tool";
      data: { id: string; name: string; ok: boolean; preview: string; queries: Query[] };
    }
  | { event: "block"; data: Block }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { usage: Usage } };
