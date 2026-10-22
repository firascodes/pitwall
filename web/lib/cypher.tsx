import type { ReactNode } from "react";

const KEYWORDS =
  /\b(MATCH|OPTIONAL|WHERE|RETURN|WITH|ORDER BY|LIMIT|CASE|WHEN|THEN|ELSE|END|AND|OR|NOT|IS|NULL|IN|AS|DESC|UNWIND|CONTAINS|DISTINCT|count|sum|max|min|coalesce|toLower|split)\b|(\$\w+)/g;

/** Cypher with keywords and $parameters coloured; plain text otherwise, never HTML. */
export function highlight(cypher: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of cypher.matchAll(KEYWORDS)) {
    parts.push(cypher.slice(last, m.index));
    parts.push(
      <span key={m.index} className={m[2] ? "par" : "kw"}>
        {m[0]}
      </span>,
    );
    last = m.index! + m[0].length;
  }
  parts.push(cypher.slice(last));
  return parts;
}
