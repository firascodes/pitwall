"use client";

import { useState } from "react";
import { code } from "@/lib/format";
import type { DeltaData } from "@/lib/types";

const W = 1000;
const H = 150;

export function DeltaChart({ data, title }: { data: DeltaData; title: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const { distance_m: d, b_behind_a_s: g } = data;
  const [a, b] = [code(data.a.driver), code(data.b.driver)];
  const span = Math.max(0.05, ...g.map(Math.abs)) * 1.15;
  const x = (m: number) => (m / d[d.length - 1]) * W;
  const y = (s: number) => H / 2 - (s / span) * (H / 2);
  const line = g.map((s, i) => `${x(d[i]).toFixed(1)},${y(s).toFixed(1)}`).join(" ");
  const final = g[g.length - 1];
  const i = hover ?? g.length - 1;

  return (
    <div className="card">
      <div className="card-head px">
        <span>{title || "Gap through the lap"}</span>
        <span className="mono" style={{ fontSize: 12, textTransform: "none" }}>
          {hover === null ? "Final" : `${Math.round(d[i]).toLocaleString()} m`}{" "}
          <b style={{ color: g[i] >= 0 ? "var(--a)" : "var(--yellow)" }}>
            {g[i] >= 0 ? a : b} +{Math.abs(g[i]).toFixed(3)}s
          </b>
        </span>
      </div>
      <div style={{ position: "relative", padding: "0 16px 12px" }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ width: "100%", height: 132, display: "block" }}
          onMouseLeave={() => setHover(null)}
          onMouseMove={(e) => {
            const box = e.currentTarget.getBoundingClientRect();
            const m = ((e.clientX - box.left) / box.width) * d[d.length - 1];
            let best = 0;
            for (let k = 1; k < d.length; k++) if (Math.abs(d[k] - m) < Math.abs(d[best] - m)) best = k;
            setHover(best);
          }}
          role="img"
          aria-label={`Gap between ${a} and ${b}: final ${final.toFixed(3)} seconds`}
        >
          <line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="var(--dim)" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" opacity=".6" />
          <polygon points={`0,${H / 2} ${line} ${W},${H / 2}`} fill="var(--a)" opacity=".1" />
          <polyline points={line} fill="none" stroke="var(--ink)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          {hover !== null && (
            <line x1={x(d[i])} x2={x(d[i])} y1="0" y2={H} stroke="var(--ink)" opacity=".3" vectorEffect="non-scaling-stroke" />
          )}
        </svg>
        <span className="px" style={{ position: "absolute", left: 20, top: 2, color: "var(--a)" }}>
          {a} ahead
        </span>
        <span className="px" style={{ position: "absolute", left: 20, bottom: 14, color: "var(--yellow)" }}>
          {b} ahead
        </span>
      </div>
    </div>
  );
}
