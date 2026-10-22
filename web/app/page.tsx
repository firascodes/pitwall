import { HeroAsk } from "@/components/HeroAsk";
import { highlight } from "@/lib/cypher";

const GITHUB = "https://github.com/firascodes/pitwall";
const BOT = process.env.NEXT_PUBLIC_TELEGRAM_BOT; // the bot's username, without @

const STATS = [
  ["28.8k", "graph nodes"],
  ["27,775", "laps with telemetry"],
  ["8/8", "golden evals passing"],
  ["$0.0008", "per lap comparison"],
];

const STEPS = [
  ["The graph finds the facts", "Drivers, results, teams and every lap live in Neo4j. Tested Cypher templates answer most questions in a few milliseconds."],
  ["Telemetry rebuilds the lap", "Speed and position every 5 metres, from OpenF1. Two laps become a replay with a ghost car and a corner-by-corner gap."],
  ["The agent picks the format", "Short text first, then only the charts that help. Each answer streams in with its sources and its cost."],
];

// The real find_lap template, trimmed to the push-lap case
const FIND_LAP = `MATCH (:Race {race_id: $race_id})-[:HAS_SESSION]->(:Session {type: $type})
      <-[:IN_SESSION]-(res:Result),
      (d:Driver {driver_id: $driver_id})-[:ACHIEVED]->(res)-[:HAS_LAP]->(l:Lap)
WHERE l.lap_time_ms IS NOT NULL AND NOT l.deleted
RETURN l.lap_id, l.lap_time_ms, l.compound, l.tyre_age
ORDER BY l.lap_time_ms LIMIT 1`;

export default function Landing() {
  return (
    <div className="landing">
      <nav className="lnav">
        <div className="wrap">
          <a href="/" aria-label="Pitwall home">
            <img src="/pitwall-logo.svg" width={76} height={52} alt="Pitwall" className="nav-logo" />
          </a>
          <div className="nav-links">
            <a href="#how">How it works</a>
            <a href="#trace">The trace</a>
            {BOT && <a href={`https://t.me/${BOT}`}>Telegram</a>}
            <a href={GITHUB}>GitHub</a>
          </div>
          <a className="nav-signin" href="/chat?signin=1">
            Sign in
          </a>
          <a className="btn-red px" href="/chat">
            Try it free
          </a>
        </div>
      </nav>

      <header className="wrap lhero">
        <div className="lhero-copy">
          <span className="px tag">
            <span className="sq" />
            F1 2026 · Rounds 1–17 · real data
          </span>
          <h1>
            Ask the
            <br />
            pit wall.
          </h1>
          <p className="lead">
            A race engineer for the 2026 season. It answers from a Neo4j knowledge graph and real telemetry, replays the lap with a ghost car, and shows every query it ran.
          </p>
          <HeroAsk />
        </div>
        <div className="shot">
          <div className="window">
            <div className="bar">
              <span className="sq" style={{ background: "var(--red)" }} />
              <span className="sq" />
              <span className="sq" />
            </div>
            <img src="/screenshot.png" width={1280} height={1300} alt="Pitwall answering a lap comparison with a replay, a corner table and a delta chart" />
          </div>
          <div className="cost-badge mono">
            <span className="px dim">This answer cost</span>
            <b>$0.000793</b>
          </div>
        </div>
      </header>

      <div className="stats">
        <div className="wrap">
          {STATS.map(([n, label]) => (
            <div key={label}>
              <span className="mono" style={label.includes("evals") ? { color: "var(--green)" } : undefined}>
                {n}
              </span>
              <span className="px dim">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <section className="wrap lsection" id="how">
        <div className="lsection-head">
          <h2>How it works</h2>
          <p className="lead">One question, three moves. Every number comes from a tool, never from the model.</p>
        </div>
        <div className="steps">
          {STEPS.map(([title, body], i) => (
            <div className="step" key={title}>
              <span className="mono num">0{i + 1}</span>
              <b>{title}</b>
              <p className="muted">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="band" id="trace">
        <div className="wrap trace-band">
          <div className="lsection-copy">
            <span className="px" style={{ color: "var(--red)" }}>
              Glass box, not black box
            </span>
            <h2>Every query, in the open.</h2>
            <p className="lead">
              Open the trace under any answer. You see each tool the agent called, the exact Cypher it sent to Neo4j, the parameters, the rows that came back and how long it took.
            </p>
          </div>
          <div className="code-card mono">
            <header>
              <span className="sq" style={{ background: "var(--green)" }} />
              <b>find_lap</b>
              <span className="muted">(driver_name=&quot;Leclerc&quot;, race=&quot;Singapore&quot;, session=&quot;Q&quot;)</span>
            </header>
            <pre>{highlight(FIND_LAP)}</pre>
            <footer>
              <span>
                <span className="par">$race_id</span>=&quot;2026-17&quot;
              </span>
              <span>
                <span className="par">$driver_id</span>=&quot;leclerc&quot;
              </span>
              <span style={{ marginLeft: "auto" }}>1 row · 9.8 ms</span>
            </footer>
          </div>
        </div>
      </section>

      <section className="wrap lsection">
        <div className="tg">
          <img src="/telegram-avatar.svg" width={108} height={108} alt="Pitwall bot" />
          <div>
            <span className="px" style={{ color: "#ffd0cb" }}>
              Also on Telegram
            </span>
            <b>Your race engineer, one message away.</b>
            <span>Ask in chat. Tap &quot;Open lap replay&quot; and the replay opens right inside Telegram.</span>
          </div>
          {BOT && (
            <a className="btn-white px" href={`https://t.me/${BOT}`}>
              Open @{BOT}
            </a>
          )}
        </div>
      </section>

      <footer className="lfoot">
        <div className="wrap">
          <img src="/pitwall-logo.svg" width={58} height={40} alt="" className="nav-logo" />
          <span>Unofficial fan project. Not affiliated with Formula 1, the FIA or any team.</span>
          <span className="credits">Data: Jolpica-F1 · OpenF1 · MultiViewer</span>
          <a href={GITHUB}>GitHub</a>
        </div>
      </footer>
    </div>
  );
}
