"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, ask, getQuota, type Quota, wake } from "@/lib/api";
import { signOut, useSession } from "@/lib/auth";
import { loadTheme, loadThreads, saveTheme, saveThreads } from "@/lib/store";
import type { AskEvent, Thread, Turn } from "@/lib/types";
import { Answer } from "./Answer";
import { Sidebar } from "./Sidebar";
import { SignIn } from "./SignIn";

const EXAMPLES = [
  "Compare Hamilton and Leclerc's fastest laps in Singapore qualifying",
  "Who leads the championship, and by how much?",
  "How has Antonelli done against Russell this season?",
  "Which laps were deleted in Monza qualifying, and why?",
];

const blank = (): Thread => ({ id: null, title: "New radio check", turns: [], updatedAt: Date.now() });

function apply(turn: Turn, e: AskEvent, step: number): Turn {
  switch (e.event) {
    case "step":
      return { ...turn, tools: [...turn.tools, ...e.data.tool_calls.map((c) => ({ ...c, step }))] };
    case "tool":
      return {
        ...turn,
        tools: turn.tools.map((t) => (t.id === e.data.id ? { ...t, ok: e.data.ok, preview: e.data.preview, queries: e.data.queries } : t)),
      };
    case "block":
      return { ...turn, blocks: [...turn.blocks, e.data] };
    case "error":
      return { ...turn, error: e.data.message };
    case "done":
      return { ...turn, usage: e.data.usage, endedAt: Date.now() };
    default:
      return turn;
  }
}

export function Chat() {
  const [threads, setThreads] = useState<Thread[]>([blank()]);
  const [active, setActive] = useState(0);
  const [running, setRunning] = useState(false);
  const [draft, setDraft] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [menu, setMenu] = useState(false);
  const [awake, setAwake] = useState(false);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [signIn, setSignIn] = useState<"guest_limit" | "nav" | null>(null);
  const feed = useRef<HTMLDivElement>(null);
  const asked = useRef(false);
  const params = useSearchParams();
  const router = useRouter();
  const session = useSession();
  const token = session?.access_token;
  const thread = threads[active];
  const locked = !!quota?.auth && !quota.signed_in && quota.used >= quota.limit;

  const refreshQuota = useCallback(() => getQuota(token).then(setQuota), [token]);
  useEffect(() => {
    refreshQuota();
    if (session) setSignIn(null);
  }, [refreshQuota, session]);

  useEffect(() => {
    const saved = loadThreads();
    if (saved.length) setThreads([blank(), ...saved.filter((t) => t.turns.length)]);
    setTheme(loadTheme());
    wake().then(setAwake);
    if (params.get("signin")) setSignIn("nav");
  }, [params]);

  // A question typed on the landing page arrives as ?q=
  useEffect(() => {
    const q = params.get("q");
    if (!q || asked.current) return;
    asked.current = true;
    router.replace("/chat");
    send(q);
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: "smooth" });
  }, [thread.turns.length, thread.turns.at(-1)?.blocks.length]);

  const update = (i: number, fn: (t: Thread) => Thread) =>
    setThreads((all) => {
      const next = all.map((t, j) => (j === i ? fn(t) : t));
      saveThreads(next.filter((t) => t.turns.length && t.turns.every((u) => u.endedAt)));
      return next;
    });

  async function send(question: string) {
    const q = question.trim();
    if (!q || running) return;
    if (locked) return setSignIn("guest_limit");
    const i = active;
    const turn: Turn = { id: crypto.randomUUID(), question: q, tools: [], blocks: [], startedAt: Date.now() };
    const patch = (fn: (t: Turn) => Turn) =>
      update(i, (t) => ({ ...t, updatedAt: Date.now(), turns: t.turns.map((u) => (u.id === turn.id ? fn(u) : u)) }));
    update(i, (t) => ({ ...t, title: t.turns.length ? t.title : q, turns: [...t.turns, turn] }));
    setDraft("");
    setRunning(true);
    let step = 0;
    try {
      await ask(
        q,
        thread.id,
        (e) => {
          setAwake(true);
          if (e.event === "start") update(i, (t) => ({ ...t, id: e.data.thread_id }));
          if (e.event === "step") step++;
          patch((u) => apply(u, e, step));
        },
        token,
      );
    } catch (err) {
      if (err instanceof ApiError && err.code === "guest_limit") setSignIn("guest_limit");
      patch((u) => ({ ...u, error: (err as Error).message, endedAt: Date.now() }));
    } finally {
      patch((u) => (u.endedAt ? u : { ...u, endedAt: Date.now() }));
      setRunning(false);
      refreshQuota();
    }
  }

  function newThread() {
    setMenu(false);
    if (!threads[0].turns.length) return setActive(0);
    setThreads((all) => [blank(), ...all]);
    setActive(0);
  }

  return (
    <div className="app">
      <Sidebar
        threads={threads}
        active={active}
        open={menu}
        quota={quota}
        email={session?.user.email ?? null}
        onSignIn={() => setSignIn("nav")}
        onSignOut={() => signOut()}
        onNew={newThread}
        onPick={(i) => {
          setActive(i);
          setMenu(false);
        }}
      />
      <main onClick={() => menu && setMenu(false)}>
        <header className="topbar">
          <button className="icon-btn menu-btn" aria-label="Menu" onClick={(e) => (e.stopPropagation(), setMenu(!menu))}>
            <svg width="14" height="12" shapeRendering="crispEdges" aria-hidden>
              <rect y="0" width="14" height="2" fill="currentColor" />
              <rect y="5" width="14" height="2" fill="currentColor" />
              <rect y="10" width="14" height="2" fill="currentColor" />
            </svg>
          </button>
          <h1>{thread.title}</h1>
          <button
            className="icon-btn"
            aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            onClick={() => {
              const next = theme === "light" ? "dark" : "light";
              setTheme(next);
              saveTheme(next);
            }}
          >
            {theme === "light" ? (
              <svg width="14" height="14" viewBox="0 0 14 14" shapeRendering="crispEdges" aria-hidden>
                <rect x="4" y="4" width="6" height="6" fill="currentColor" />
                {[[6, 0], [6, 12], [0, 6], [12, 6], [1.5, 1.5], [10.5, 10.5], [10.5, 1.5], [1.5, 10.5]].map(([x, y]) => (
                  <rect key={`${x}-${y}`} x={x} y={y} width="2" height="2" fill="currentColor" />
                ))}
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 14 14" shapeRendering="crispEdges" aria-hidden>
                <rect x="4" y="1" width="6" height="2" fill="currentColor" />
                <rect x="2" y="3" width="4" height="8" fill="currentColor" />
                <rect x="4" y="11" width="6" height="2" fill="currentColor" />
                <rect x="10" y="9" width="2" height="2" fill="currentColor" />
              </svg>
            )}
          </button>
        </header>
        <div className="scroll" ref={feed}>
          {thread.turns.length === 0 ? (
            <div className="hero">
              <h2>What do you need from the pit wall?</h2>
              <p>
                Your race engineer for the 2026 season. Ask about results, teammates or any lap: the answer comes
                from a Neo4j knowledge graph and real telemetry, and you can see every query it ran.
              </p>
              <div className="examples">
                {EXAMPLES.map((q) => (
                  <button key={q} className="chip" onClick={() => send(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="feed">
              {thread.turns.map((t, j) => (
                <Answer
                  key={t.id}
                  turn={t}
                  running={running && j === thread.turns.length - 1}
                  waking={!awake}
                  onAsk={send}
                />
              ))}
            </div>
          )}
        </div>
        <div className="composer">
          {locked ? (
            <button className="locked" onClick={() => setSignIn("guest_limit")}>
              Sign in to ask another question
              <span className="send px">Sign in</span>
            </button>
          ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask the pit wall…"
              maxLength={500}
              aria-label="Your question"
            />
            <button className="send px" disabled={running || !draft.trim()}>
              Box box
            </button>
          </form>
          )}
        </div>
      </main>
      <SignIn open={signIn !== null} reason={signIn ?? undefined} onClose={() => setSignIn(null)} />
    </div>
  );
}
