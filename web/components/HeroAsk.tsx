"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const EXAMPLES = [
  ["Hamilton vs Leclerc, Singapore Q3", "Compare Hamilton and Leclerc's fastest laps in Singapore qualifying"],
  ["Antonelli vs Russell", "How has Antonelli done against Russell this season?"],
  ["Deleted laps at Monza", "Which laps were deleted in Monza qualifying, and why?"],
];

/** The landing page's question box: it hands the question to /chat, which asks it. */
export function HeroAsk() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const go = (question: string) => question.trim() && router.push(`/chat?q=${encodeURIComponent(question.trim())}`);
  return (
    <>
      <form
        className="hero-ask"
        onSubmit={(e) => {
          e.preventDefault();
          go(q);
        }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Who leads the championship?" aria-label="Your question" maxLength={500} />
        <button className="send px">Box box</button>
      </form>
      <span className="free">
        <span className="sq" style={{ background: "var(--green)" }} />
        One free question, no sign-up. Sign in for more.
      </span>
      <div className="hero-chips">
        {EXAMPLES.map(([label, question]) => (
          <button key={label} className="chip" onClick={() => go(question)}>
            {label}
          </button>
        ))}
      </div>
    </>
  );
}
