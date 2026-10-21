"use client";

import { useEffect, useRef, useState } from "react";
import { getLap, type LapTelemetry } from "@/lib/api";
import { code } from "@/lib/format";
import type { ReplayData } from "@/lib/types";

const RATES = [0.5, 1, 2, 4];

/** Index of the last sample at or before x (xs ascending). */
function seek(xs: number[], x: number): number {
  let lo = 0;
  let hi = xs.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

function at(lap: LapTelemetry, key: keyof LapTelemetry, by: number[], x: number): number {
  const ys = lap[key] as number[];
  const i = seek(by, x);
  if (i >= by.length - 1) return ys[ys.length - 1];
  const f = (x - by[i]) / (by[i + 1] - by[i] || 1);
  return ys[i] + (ys[i + 1] - ys[i]) * f;
}

function colors(el: Element) {
  const css = getComputedStyle(el);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return { track: v("--track"), a: v("--a"), b: v("--b"), panel: v("--panel"), ink: v("--ink"), ghost: v("--ghost-fill") };
}

type Props = { data: ReplayData; title?: string; height?: number };

export function LapReplay({ data, title, height = 260 }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [laps, setLaps] = useState<LapTelemetry[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [, redraw] = useState(0);

  const ids = data.laps.join(",");
  useEffect(() => {
    Promise.all(ids.split(",").map(getLap))
      .then(setLaps)
      .catch(() => setFailed(true));
  }, [ids]);

  const [a, b] = laps ?? [];
  const duration = a ? Math.max(...laps!.map((l) => l.time_s[l.time_s.length - 1])) : 0;

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    let frame = requestAnimationFrame(function tick(now) {
      const dt = ((now - last) / 1000) * rate;
      last = now;
      setT((prev) => {
        const next = prev + dt;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [playing, rate, duration]);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const observer = new ResizeObserver(() => redraw((n) => n + 1));
    observer.observe(el);
    const themes = new MutationObserver(() => redraw((n) => n + 1));
    themes.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      observer.disconnect();
      themes.disconnect();
    };
  }, []);

  useEffect(() => {
    const el = canvas.current;
    if (!el || !a) return;
    const dpr = window.devicePixelRatio || 1;
    const w = el.clientWidth;
    const h = el.clientHeight;
    el.width = Math.round(w * dpr);
    el.height = Math.round(h * dpr);
    const ctx = el.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const c = colors(el);

    const pad = 28;
    const [minX, maxX] = [Math.min(...a.x_m), Math.max(...a.x_m)];
    const [minY, maxY] = [Math.min(...a.y_m), Math.max(...a.y_m)];
    const scale = Math.min((w - pad * 2) / (maxX - minX || 1), (h - pad * 2) / (maxY - minY || 1));
    const ox = (w - (maxX - minX) * scale) / 2;
    const oy = (h - (maxY - minY) * scale) / 2;
    const px = (x: number) => Math.round(ox + (x - minX) * scale);
    const py = (y: number) => Math.round(h - oy - (y - minY) * scale);

    const path = (lap: LapTelemetry, upto: number) => {
      ctx.beginPath();
      for (let i = 0; i <= upto; i++) {
        const [x, y] = [px(lap.x_m[i]), py(lap.y_m[i])];
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
    };
    ctx.lineJoin = "miter";
    path(a, a.x_m.length - 1);
    ctx.closePath();
    ctx.strokeStyle = c.track;
    ctx.lineWidth = 12;
    ctx.stroke();

    path(a, seek(a.time_s, t));
    ctx.strokeStyle = c.a;
    ctx.globalAlpha = 0.6;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // start/finish: a small checkered flag
    const [sx, sy] = [px(a.x_m[0]), py(a.y_m[0])];
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 2; j++) {
        ctx.fillStyle = (i + j) % 2 ? c.panel : c.ink;
        ctx.fillRect(sx + 10 + i * 4, sy - 4 + j * 4, 4, 4);
      }

    const [x, y] = [px(at(a, "x_m", a.time_s, t)), py(at(a, "y_m", a.time_s, t))];
    ctx.fillStyle = c.a;
    ctx.fillRect(x - 7, y - 7, 14, 14);
    ctx.strokeStyle = c.panel;
    ctx.lineWidth = 2;
    ctx.strokeRect(x - 7, y - 7, 14, 14);
    if (b) {
      const [gx, gy] = [px(at(b, "x_m", b.time_s, t)), py(at(b, "y_m", b.time_s, t))];
      ctx.fillStyle = c.ghost && c.ghost !== "transparent" ? c.ghost : "rgba(0,0,0,0)";
      ctx.fillRect(gx - 6, gy - 6, 12, 12);
      ctx.setLineDash([3, 2]);
      ctx.strokeStyle = c.b;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(gx - 6, gy - 6, 12, 12);
      ctx.setLineDash([]);
    }
  });

  const names = data.drivers.map(code);
  const distance = a ? at(a, "distance_m", a.time_s, t) : 0;
  let gap: { leader: number; s: number } | null = null;
  if (a && b && t > 0) {
    const behind = at(b, "time_s", b.distance_m, distance) - t;
    gap = { leader: behind >= 0 ? 0 : 1, s: Math.abs(behind) };
  }

  return (
    <div className="card">
      <div className="card-head px">
        <span>{title ?? "Lap replay"}</span>
        <span className="legend">
          <span>
            <span className="sw-a" />
            {names[0]} <span className="mono dim">{data.times[0]}</span>
          </span>
          {data.ghost && names[1] && (
            <span>
              <span className="sw-b" />
              {names[1]} <span className="mono dim">{data.times[1]}</span>
            </span>
          )}
        </span>
      </div>
      <div className="replay-stage" style={{ height }}>
        <canvas ref={canvas} aria-label={`Replay of ${data.drivers.join(" and ")}`} />
        {failed && <div className="readout dim">Telemetry is not available for this lap.</div>}
        {!laps && !failed && <div className="readout px dim">Loading telemetry…</div>}
        {a && (
          <div className="readout">
            <span className="px dim">{Math.round(distance).toLocaleString()} m</span>
            {gap && (
              <span className="mono big" style={{ color: gap.leader ? "var(--yellow)" : "var(--a)" }}>
                {names[gap.leader]} +{gap.s.toFixed(2)}s
              </span>
            )}
          </div>
        )}
        {a && (
          <div className="speeds">
            {laps!.map((lap, i) => (
              <div key={lap.lap_id} style={{ display: "flex", flexDirection: "column" }}>
                <span className="px dim">{names[i]}</span>
                <span className="mono">{Math.round(at(lap, "speed_kph", lap.time_s, t))} kph</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="controls">
        <button
          className="play"
          aria-label={playing ? "Pause" : "Play"}
          disabled={!a}
          onClick={() => {
            if (t >= duration) setT(0);
            setPlaying(!playing);
          }}
        >
          <svg width="10" height="12" shapeRendering="crispEdges" aria-hidden>
            {playing ? (
              <>
                <rect x="0" y="0" width="3" height="12" fill="#fff" />
                <rect x="6" y="0" width="3" height="12" fill="#fff" />
              </>
            ) : (
              <>
                <rect x="0" y="0" width="2" height="12" fill="#fff" />
                <rect x="2" y="2" width="2" height="8" fill="#fff" />
                <rect x="4" y="4" width="2" height="4" fill="#fff" />
                <rect x="6" y="5" width="2" height="2" fill="#fff" />
              </>
            )}
          </svg>
        </button>
        <input
          className="scrub"
          type="range"
          min={0}
          max={duration || 1}
          step={0.01}
          value={t}
          aria-label="Lap position"
          onChange={(e) => {
            setPlaying(false);
            setT(Number(e.target.value));
          }}
        />
        <span>
          {RATES.map((r) => (
            <button key={r} className={`rate mono${r === rate ? " on" : ""}`} onClick={() => setRate(r)}>
              {r}×
            </button>
          ))}
        </span>
      </div>
    </div>
  );
}
