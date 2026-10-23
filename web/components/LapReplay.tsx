"use client";

import { useEffect, useRef, useState } from "react";
import { getLap, type LapTelemetry } from "@/lib/api";
import { code } from "@/lib/format";
import type { ReplayData } from "@/lib/types";

const RATES = [0.5, 1, 2, 4];
const SECTORS = ["S1", "S2", "S3"];

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
  return {
    track: v("--track"),
    red: v("--red"),
    green: v("--green"),
    panel: v("--panel"),
    ink: v("--ink"),
    dim: v("--dim"),
    px: v("--font-px"), // canvas fonts cannot read CSS variables, so pass the real family
    mono: v("--font-mono"),
  };
}

/** Official sector times -> elapsed seconds at the end of S1, S2 and the lap. */
function splits(sectors: (number | null)[] | null | undefined): number[] | null {
  if (!sectors || sectors.length !== 3 || sectors.some((s) => s == null)) return null;
  const [s1, s2, s3] = sectors as number[];
  return [s1 / 1000, (s1 + s2) / 1000, (s1 + s2 + s3) / 1000];
}

const fmt = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}:${(s % 60).toFixed(3).padStart(6, "0")}` : s.toFixed(3));

type Props = { data: ReplayData; title?: string; height?: number };

export function LapReplay({ data, title, height = 300 }: Props) {
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
  const duration = laps ? Math.max(...laps.map((l) => l.time_s[l.time_s.length - 1])) : 0;
  const names = data.drivers.map(code);
  const cuts = data.laps.map((_, i) => splits(data.sectors_ms?.[i]));

  // Who is ahead right now: B's time at A's distance, minus now
  const distance = a ? at(a, "distance_m", a.time_s, t) : 0;
  const behind = a && b && t > 0 ? at(b, "time_s", b.distance_m, distance) - t : 0;
  const leader = behind >= 0 ? 0 : 1;

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

    const pad = 34;
    const [minX, maxX] = [Math.min(...a.x_m), Math.max(...a.x_m)];
    const [minY, maxY] = [Math.min(...a.y_m), Math.max(...a.y_m)];
    const scale = Math.min((w - pad * 2) / (maxX - minX || 1), (h - pad * 2) / (maxY - minY || 1));
    const ox = (w - (maxX - minX) * scale) / 2;
    const oy = (h - (maxY - minY) * scale) / 2;
    const px = (x: number) => Math.round(ox + (x - minX) * scale);
    const py = (y: number) => Math.round(h - oy - (y - minY) * scale);
    const point = (lap: LapTelemetry, d: number) => [px(at(lap, "x_m", lap.distance_m, d)), py(at(lap, "y_m", lap.distance_m, d))];

    ctx.beginPath();
    a.x_m.forEach((x, i) => (i ? ctx.lineTo(px(x), py(a.y_m[i])) : ctx.moveTo(px(x), py(a.y_m[i]))));
    ctx.closePath();
    ctx.lineJoin = "miter";
    ctx.strokeStyle = c.track;
    ctx.lineWidth = 12;
    ctx.stroke();

    // sector lines where car A crossed S1 and S2
    ctx.font = `9px ${c.px}, monospace`;
    cuts[0]?.slice(0, 2).forEach((s, i) => {
      const d = at(a, "distance_m", a.time_s, s);
      const [x, y] = point(a, d);
      const [nx, ny] = point(a, d + 15);
      const len = Math.hypot(nx - x, ny - y) || 1;
      const [ux, uy] = [-(ny - y) / len, (nx - x) / len];
      ctx.strokeStyle = c.ink;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x - ux * 9, y - uy * 9);
      ctx.lineTo(x + ux * 9, y + uy * 9);
      ctx.stroke();
      ctx.fillStyle = c.dim;
      ctx.fillText(SECTORS[i + 1], x + ux * 14 - 6, y + uy * 14 + 3);
    });

    // start/finish: a small checkered flag
    const [sx, sy] = [px(a.x_m[0]), py(a.y_m[0])];
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 2; j++) {
        ctx.fillStyle = (i + j) % 2 ? c.panel : c.ink;
        ctx.fillRect(sx + 10 + i * 4, sy - 4 + j * 4, 4, 4);
      }

    // cars: the one ahead right now is green, the one behind red; the trailing car draws first
    const order = b ? (leader === 0 ? [1, 0] : [0, 1]) : [0];
    for (const k of order) {
      const lap = laps![k];
      const [x, y] = [px(at(lap, "x_m", lap.time_s, t)), py(at(lap, "y_m", lap.time_s, t))];
      ctx.fillStyle = !b ? c.red : k === leader ? c.green : c.red;
      ctx.fillRect(x - 7, y - 7, 14, 14);
      ctx.strokeStyle = c.panel;
      ctx.lineWidth = 2;
      ctx.strokeRect(x - 7, y - 7, 14, 14);
      const label = b && k !== leader && t > 0 ? `${names[k]} +${Math.abs(behind).toFixed(2)}` : names[k];
      ctx.font = `600 11px ${c.mono}, monospace`;
      const tw = ctx.measureText(label).width + 8;
      const ly = k === 0 ? y - 26 : y + 12;
      ctx.fillStyle = c.ink;
      ctx.fillRect(x + 10, ly, tw, 16);
      ctx.fillStyle = c.panel;
      ctx.fillText(label, x + 14, ly + 12);
    }
  });

  const shown = (k: number, j: number) => (cuts[k] && t >= cuts[k]![j] ? cuts[k]![j] - (j ? cuts[k]![j - 1] : 0) : null);
  const cell = (k: number, j: number) => {
    const mine = j < 3 ? shown(k, j) : cuts[k] && t >= cuts[k]![2] ? cuts[k]![2] : null;
    if (mine === null) return { text: "–", color: "var(--dim)" };
    const other = b ? (j < 3 ? shown(1 - k, j) : cuts[1 - k] && t >= cuts[1 - k]![2] ? cuts[1 - k]![2] : null) : null;
    if (other === null) return { text: fmt(mine), color: "var(--ink)" };
    return { text: fmt(mine), color: mine <= other ? "var(--green)" : "var(--red)" };
  };

  return (
    <div className="card replay">
      <div className="card-head px">
        <span>{title ?? "Lap replay"}</span>
        {b && t > 0 && (
          <span className="mono gap-now" style={{ color: "var(--green)" }}>
            {names[leader]} ahead +{Math.abs(behind).toFixed(2)}s
          </span>
        )}
      </div>
      <div className="replay-stage" style={{ height }}>
        <canvas ref={canvas} aria-label={`Replay of ${data.drivers.join(" and ")}`} />
        {failed && <div className="readout dim">Telemetry is not available for this lap.</div>}
        {!laps && !failed && <div className="readout px dim">Loading telemetry…</div>}
        {laps && (
          <div className="speeds">
            <span className="px dim">{Math.round(distance).toLocaleString()} m</span>
            {laps.map((lap, k) => (
              <div key={lap.lap_id}>
                <span className="px dim">{names[k]}</span>
                <span className="mono">{Math.round(at(lap, "speed_kph", lap.time_s, t))} kph</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {laps && cuts.some(Boolean) && (
          <table className="tower mono" aria-label="Sector times">
            <thead>
              <tr>
                <th />
                {[...SECTORS, "Lap"].map((s) => (
                  <th key={s}>{s}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {laps.map((lap, k) => (
                <tr key={lap.lap_id}>
                  <th>{names[k]}</th>
                  {[0, 1, 2, 3].map((j) => {
                    const { text, color } = cell(k, j);
                    return (
                      <td key={j} style={{ color }}>
                        {text}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
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
