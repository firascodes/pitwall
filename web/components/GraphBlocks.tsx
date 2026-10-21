"use client";

import { useState } from "react";
import type { Row } from "@/lib/types";

const MAX_ROWS = 10;
const label = (key: string) => key.replace(/_/g, " ");
const show = (v: unknown) => (Array.isArray(v) ? v.join("–") : v === null || v === undefined ? "" : String(v));

export function ResultsTable({ rows, title }: { rows: Row[]; title: string }) {
  const [all, setAll] = useState(false);
  const columns = [...new Set(rows.flatMap((r) => Object.keys(r)))].filter((c) => c !== "lap_id");
  return (
    <div className="card">
      <div className="card-head px">
        <span>{title}</span>
        <span className="dim">{rows.length} rows</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{label(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(all ? rows : rows.slice(0, MAX_ROWS)).map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c} className={typeof r[c] === "number" || /^\d+:\d/.test(show(r[c])) ? "num" : ""}>
                    {show(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > MAX_ROWS && (
        <button className="more" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `All ${rows.length} rows →`}
        </button>
      )}
    </div>
  );
}

function Battle({ name, pair }: { name: string; pair: unknown }) {
  if (!Array.isArray(pair) || pair[0] + pair[1] === 0) return null;
  const [me, them] = pair as [number, number];
  return (
    <div className="h2h-row">
      <span className="px dim">{name}</span>
      <div className="bar">
        <div className="me" style={{ flex: me || 0.001 }} />
        <div className="them" style={{ flex: them || 0.001 }} />
      </div>
      <span className="mono" style={{ textAlign: "right" }}>
        {me}–{them}
      </span>
    </div>
  );
}

export function H2HCard({ rows, title }: { rows: Row[]; title: string }) {
  return (
    <>
      {rows.map((r, i) => {
        const gap = Number(r.avg_quali_gap_pct ?? 0);
        return (
          <div className="card h2h" key={i}>
            <div className="card-head px">
              <span>
                {title || "Teammate battle"} · {show(r.driver)} vs {show(r.teammate)}
              </span>
              <span className="dim">{show(r.team)}</span>
            </div>
            <Battle name="Quali" pair={r.quali_h2h} />
            <Battle name="Race" pair={r.race_h2h} />
            <Battle name="Sprint" pair={r.sprint_h2h} />
            <div className="h2h-row">
              <span className="px dim">Avg gap</span>
              <span className="muted" style={{ fontSize: 13 }}>
                Qualifying, {show(r.sessions_together)} sessions together
              </span>
              <span className="mono" style={{ textAlign: "right", color: gap <= 0 ? "var(--green)" : "var(--yellow)" }}>
                {gap > 0 ? "+" : ""}
                {gap.toFixed(2)}%
              </span>
            </div>
          </div>
        );
      })}
    </>
  );
}

export function StintTimeline({ stints, title }: { stints: Row[]; title: string }) {
  const last = Math.max(...stints.map((s) => Number(s.to_round)));
  return (
    <div className="card">
      <div className="card-head px">
        <span>{title || "Teams this season"}</span>
        <span className="dim">R1–R{last}</span>
      </div>
      <div className="stints">
        <div className="stint-track">
          {stints.map((s, i) => {
            const from = Number(s.from_round);
            const to = Number(s.to_round);
            return (
              <div
                key={i}
                className="stint"
                title={`${show(s.team)}: rounds ${from}–${to}`}
                style={{ left: `${((from - 1) / last) * 100}%`, width: `${((to - from + 1) / last) * 100}%` }}
              >
                {show(s.team)} · R{from}–R{to}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
