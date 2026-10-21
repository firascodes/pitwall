"use client";

import { usd } from "@/lib/format";
import type { Block, Turn } from "@/lib/types";
import { AnswerText } from "./AnswerText";
import { CornerTable } from "./CornerTable";
import { DeltaChart } from "./DeltaChart";
import { H2HCard, ResultsTable, StintTimeline } from "./GraphBlocks";
import { LapReplay } from "./LapReplay";
import { Trace } from "./Trace";

function Component({ block }: { block: Block }) {
  switch (block.type) {
    case "lap_replay":
      return <LapReplay data={block.data} title={block.title} />;
    case "delta_chart":
      return <DeltaChart data={block.data} title={block.title} />;
    case "corner_table":
      return <CornerTable data={block.data} title={block.title} />;
    case "results_table":
      return <ResultsTable rows={block.data.rows} title={block.title} />;
    case "h2h_card":
      return <H2HCard rows={block.data.rows} title={block.title} />;
    case "stint_timeline":
      return <StintTimeline stints={block.data.stints} title={block.title} />;
    default:
      return null;
  }
}

/** The composer sends replay + corner table side by side when both are there. */
function Components({ blocks }: { blocks: Block[] }) {
  const out: React.ReactNode[] = [];
  for (let i = 0; i < blocks.length; i++) {
    const [b, next] = [blocks[i], blocks[i + 1]];
    if (b.type === "lap_replay" && next?.type === "corner_table") {
      out.push(
        <div className="grid2" key={i}>
          <Component block={b} />
          <Component block={next} />
        </div>,
      );
      i++;
    } else out.push(<Component block={b} key={i} />);
  }
  return <>{out}</>;
}

/** Replay first, then the table beside it, then the chart: the layout from the mockup. */
function order(blocks: Block[]): Block[] {
  const rank: Record<string, number> = { lap_replay: 0, corner_table: 1, delta_chart: 2 };
  return [...blocks].sort((x, y) => (rank[x.type] ?? 3) - (rank[y.type] ?? 3));
}

export function Answer({ turn, running, onAsk }: { turn: Turn; running: boolean; onAsk: (q: string) => void }) {
  const done = turn.tools.filter((t) => t.ok);
  const sources = Object.fromEntries(done.map((t, i) => [`r${i + 1}`, t.name]));
  const texts = turn.blocks.filter((b) => b.type === "text");
  const components = order(turn.blocks.filter((b) => b.type !== "text" && b.type !== "chips"));
  const chips = turn.blocks.find((b) => b.type === "chips");
  const u = turn.usage;

  return (
    <section className="turn">
      <div className="question">{turn.question}</div>
      <Trace tools={turn.tools} running={running} ms={turn.endedAt ? turn.endedAt - turn.startedAt : undefined} />
      {texts.map((b, i) => b.type === "text" && <AnswerText key={i} text={b.text} sources={sources} />)}
      <Components blocks={components} />
      {turn.error && <div className="error">{turn.error}</div>}
      {(chips || u) && (
        <div className="foot">
          <div className="chips">
            {chips?.type === "chips" &&
              chips.options.map((o) => (
                <button key={o} className="chip" onClick={() => onAsk(o)} disabled={running}>
                  {o}
                </button>
              ))}
          </div>
          {u && (
            <span
              className="cost mono"
              data-usd={u.usd}
              title={`${u.input_tokens.toLocaleString()} in · ${u.cached_tokens.toLocaleString()} cached · ${u.output_tokens.toLocaleString()} out (${u.reasoning_tokens} reasoning)`}
            >
              <b>{usd(u.usd)}</b> · {u.llm_calls} calls
            </span>
          )}
        </div>
      )}
    </section>
  );
}
