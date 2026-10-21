import { Fragment, type ReactNode } from "react";

/** Tiny markdown: paragraphs, "- " lists, **bold**, and [r1] citations. The text is never HTML. */
function inline(text: string, sources: Record<string, string>): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\[r\d+(?:,\s*r\d+)*\])/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    const cites = part.match(/^\[(r\d+(?:,\s*r\d+)*)\]$/);
    if (cites) {
      const ids = cites[1].split(/,\s*/);
      return (
        <span key={i} className="cite" title={ids.map((id) => `${id}: ${sources[id] ?? "tool result"}`).join("\n")}>
          {ids.map((id) => id.slice(1)).join(" ")}
        </span>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function AnswerText({ text, sources }: { text: string; sources: Record<string, string> }) {
  const paragraphs = text.trim().split(/\n{2,}/);
  return (
    <div className="answer-text">
      {paragraphs.map((p, i) => {
        const lines = p.split("\n");
        if (lines.every((l) => /^\s*[-*] /.test(l)))
          return (
            <ul key={i}>
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*[-*] /, ""), sources)}</li>
              ))}
            </ul>
          );
        return <p key={i}>{inline(lines.join(" "), sources)}</p>;
      })}
    </div>
  );
}
