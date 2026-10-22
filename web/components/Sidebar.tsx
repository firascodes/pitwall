"use client";

import { useEffect, useRef, useState } from "react";
import { getDemoUsage, type DemoUsage, type Quota } from "@/lib/api";
import { usd } from "@/lib/format";
import type { Thread } from "@/lib/types";

type Props = {
  threads: Thread[];
  active: number;
  open: boolean;
  quota: Quota | null;
  email: string | null;
  onPick: (i: number) => void;
  onNew: () => void;
  onSignIn: () => void;
  onSignOut: () => void;
};

function Account({ quota, email, onSignIn, onSignOut }: Pick<Props, "quota" | "email" | "onSignIn" | "onSignOut">) {
  if (!quota?.auth) return null;
  if (email)
    return (
      <div className="account">
        <span title={email}>{email}</span>
        <span className="mono dim">
          {quota.limit - quota.used} of {quota.limit} left today
        </span>
        <button className="dim" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    );
  const left = Math.max(0, quota.limit - quota.used);
  return (
    <>
      <div className="guest">
        <div className="kv">
          <span className="px">Guest</span>
          <b>
            {left} of {quota.limit} left
          </b>
        </div>
        <div className="meter">
          <div style={{ width: `${(left / quota.limit) * 100}%` }} />
        </div>
        <span className="muted" style={{ fontSize: 13 }}>
          Sign in for 30 questions a day.
        </span>
      </div>
      <button className="send px" style={{ height: 40 }} onClick={onSignIn}>
        Sign in
      </button>
    </>
  );
}

function Usage({ threads }: { threads: Thread[] }) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [demo, setDemo] = useState<DemoUsage | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const turns = threads.flatMap((t) => t.turns).filter((t) => t.usage);
  const spent = turns.reduce((s, t) => s + t.usage!.usd, 0);
  const tokens = turns.reduce((s, t) => s + t.usage!.input_tokens + t.usage!.output_tokens, 0);
  const shown = open || pinned;

  useEffect(() => {
    if (shown) getDemoUsage().then(setDemo);
  }, [shown, turns.length]);

  useEffect(() => {
    if (!pinned) return;
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setPinned(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [pinned]);

  return (
    <div ref={box} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      {shown && (
        <div className="popover" role="dialog" aria-label="Usage">
          <div className="kv" style={{ alignItems: "baseline" }}>
            <span className="px">Spent here</span>
            <span className="mono" style={{ fontSize: 18, fontWeight: 600, color: "var(--ink)" }}>
              {usd(spent)}
            </span>
          </div>
          <div className="kv">
            <span>Answers</span>
            <b>{turns.length}</b>
          </div>
          <div className="kv">
            <span>Avg per answer</span>
            <b>{turns.length ? usd(spent / turns.length) : "–"}</b>
          </div>
          <div className="kv">
            <span>Tokens</span>
            <b>{tokens.toLocaleString()}</b>
          </div>
          {demo && (
            <div style={{ borderTop: "1px solid var(--line)", paddingTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              <div className="kv">
                <span>Demo today</span>
                <b>
                  {usd(demo.spent_usd)} / ${demo.cap_usd.toFixed(2)}
                </b>
              </div>
              <div className="meter">
                <div style={{ width: `${Math.min(100, (demo.spent_usd / demo.cap_usd) * 100)}%` }} />
              </div>
            </div>
          )}
        </div>
      )}
      <button className="usage-btn" aria-expanded={shown} onClick={() => setPinned(!pinned)}>
        <svg width="16" height="16" viewBox="0 0 16 16" shapeRendering="crispEdges" aria-hidden>
          <rect x="2" y="10" width="3" height="4" fill="currentColor" />
          <rect x="6.5" y="6" width="3" height="8" fill="currentColor" />
          <rect x="11" y="2" width="3" height="12" fill="var(--red)" />
        </svg>
        Usage
        <svg style={{ marginLeft: "auto", transform: shown ? undefined : "rotate(180deg)" }} width="8" height="6" shapeRendering="crispEdges" aria-hidden>
          <rect x="0" y="4" width="8" height="2" fill="currentColor" />
          <rect x="2" y="2" width="4" height="2" fill="currentColor" />
          <rect x="3" y="0" width="2" height="2" fill="currentColor" />
        </svg>
      </button>
    </div>
  );
}

export function Sidebar({ threads, active, open, onPick, onNew, ...account }: Props) {
  return (
    <aside className={`sidebar${open ? " open" : ""}`}>
      <a href="/" aria-label="Pitwall home">
        <img className="logo" src="/pitwall-logo.svg" alt="Pitwall" width={200} height={137} />
      </a>
      <button className="btn-retro px" onClick={onNew}>
        <svg width="10" height="10" shapeRendering="crispEdges" aria-hidden>
          <rect x="4" y="0" width="2" height="10" fill="currentColor" />
          <rect x="0" y="4" width="10" height="2" fill="currentColor" />
        </svg>
        New radio check
      </button>
      <nav className="threads" aria-label="Recent questions">
        {threads.some((t) => t.turns.length) && <div className="px dim" style={{ padding: "0 12px 8px" }}>Recent</div>}
        {threads.map(
          (t, i) =>
            t.turns.length > 0 && (
              <button key={t.id ?? i} className={`thread${i === active ? " on" : ""}`} onClick={() => onPick(i)} title={t.title}>
                {t.title}
              </button>
            ),
        )}
      </nav>
      <Account {...account} />
      <Usage threads={threads} />
    </aside>
  );
}
