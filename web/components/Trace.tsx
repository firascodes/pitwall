"use client";

import { Fragment, useState } from "react";
import { plural, seconds } from "@/lib/format";
import { highlight } from "@/lib/cypher";
import type { Query, ToolCall } from "@/lib/types";

/** Name a query by its shape: entity resolution runs before every tool's main query. */
function purpose(cypher: string, tool: string) {
  if (cypher.startsWith("MATCH (d:Driver)\nWITH d, CASE")) return "find driver";
  if (/^MATCH \(r:Race \{season: \$season\}\)-\[:AT\]/.test(cypher) || cypher.includes("ORDER BY r.round DESC LIMIT 1"))
    return "find race";
  if (cypher.includes("{lap_id: $lap_id}")) return "lap facts";
  return tool;
}

function Cypher({ q, tool }: { q: Query; tool: string }) {
  const parts = highlight(q.cypher);
  const params = Object.entries(q.params).filter(([, v]) => v !== null);
  const name = purpose(q.cypher, tool);
  return (
    <details className="cypher mono" open={name === tool}>
      <summary>
        <span className="kw">{name}</span>
        {params.map(([k, v]) => (
          <span key={k}>
            <span className="par">${k}</span>={JSON.stringify(v)}
          </span>
        ))}
        <span style={{ marginLeft: "auto" }}>
          {plural(q.rows, "row")} · {q.ms} ms
        </span>
      </summary>
      <pre>{parts}</pre>
    </details>
  );
}

function args(a: Record<string, unknown>) {
  return Object.entries(a)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");
}

type Props = { tools: ToolCall[]; running: boolean; waking: boolean; ms?: number };

export function Trace({ tools, running, waking, ms }: Props) {
  const [open, setOpen] = useState(false);
  const steps = [...new Set(tools.map((t) => t.step))];
  const queries = tools.reduce((n, t) => n + (t.queries?.length ?? 0), 0);
  const current = tools.findLast((t) => t.ok === undefined);

  let summary = waking ? "Waking the pit wall (free server, up to a minute)…" : "Thinking…";
  if (running && current) summary = `Running ${current.name}…`;
  else if (!running) summary = tools.length ? `Checked ${plural(tools.length, "tool")} · ${plural(queries, "query")}` : "Answered from the conversation";
  if (!running && ms) summary += ` · ${seconds(ms)}`;

  return (
    <div className="trace">
      <button className="trace-line px" onClick={() => setOpen(!open)} aria-expanded={open} disabled={!tools.length}>
        {running ? (
          <span className="dot run" />
        ) : (
          <svg width="6" height="8" shapeRendering="crispEdges" style={{ transform: open ? "rotate(90deg)" : undefined }} aria-hidden>
            <rect x="0" y="0" width="2" height="8" fill="currentColor" />
            <rect x="2" y="2" width="2" height="4" fill="currentColor" />
            <rect x="4" y="3" width="2" height="2" fill="currentColor" />
          </svg>
        )}
        {summary}
      </button>
      {open && (
        <div className="trace-body">
          {steps.map((step, i) => {
            const calls = tools.filter((t) => t.step === step);
            return (
              <Fragment key={step}>
                <span className="px dim">
                  Step {i + 1}
                  {calls.length > 1 ? ` · ${calls.length} tools in parallel` : ""}
                </span>
                {calls.map((t) => (
                  <div className="trace-tool" key={t.id}>
                    <header>
                      <span className={`dot ${t.ok === undefined ? "run" : t.ok ? "ok" : "fail"}`} />
                      <b className="mono">{t.name}</b>
                      <span className="mono args">({args(t.args)})</span>
                    </header>
                    {t.ok === false && <span className="mono dim" style={{ fontSize: 12 }}>{t.preview}</span>}
                    {t.queries?.map((q, j) => <Cypher key={j} q={q} tool={t.name} />)}
                  </div>
                ))}
              </Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}
