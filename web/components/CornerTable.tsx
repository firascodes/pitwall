"use client";

import { useState } from "react";
import { code } from "@/lib/format";
import type { CornerData } from "@/lib/types";

const TOP = 5;

const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function CornerTable({ data, title }: { data: CornerData; title: string }) {
  const [all, setAll] = useState(false);
  const [a, b] = [code(data.a.driver), code(data.b.driver)];
  const rows = all
    ? [...data.rows].sort((x, y) => x.distance_m - y.distance_m)
    : [...data.rows].sort((x, y) => Math.abs(y.a_gain_s) - Math.abs(x.a_gain_s)).slice(0, TOP);

  return (
    <div className="card rows">
      <div className="card-head px">
        <span>{title || "Biggest swings"}</span>
        {all && <span className="dim">min kph {a} / {b}</span>}
      </div>
      {rows.map((r) => {
        const aWins = r.a_gain_s >= 0;
        return (
          <div className="row" key={r.corner}>
            <span className="px" style={{ width: 38, fontSize: 12 }}>
              {r.corner}
            </span>
            <span className="mono" style={{ width: 100, fontWeight: 600, color: aWins ? "var(--a)" : "var(--yellow)" }}>
              {aWins ? a : b} {Math.abs(r.a_gain_s).toFixed(3)}
            </span>
            {all && (
              <span className="mono muted" style={{ width: 78, fontSize: 13 }}>
                {Math.round(r.a_min_kph)} / {Math.round(r.b_min_kph)}
              </span>
            )}
            <span className="muted" style={{ flex: 1 }}>
              {sentence(r.cause)}
            </span>
          </div>
        );
      })}
      {data.rows.length > TOP && (
        <button className="more" onClick={() => setAll(!all)}>
          {all ? "Top corners only" : `All ${data.rows.length} corners →`}
        </button>
      )}
    </div>
  );
}
