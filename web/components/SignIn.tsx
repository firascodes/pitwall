"use client";

import { useEffect, useState } from "react";
import { emailLink, signInWith } from "@/lib/auth";

// Providers switched on in Supabase, e.g. NEXT_PUBLIC_AUTH_PROVIDERS=google,github
const PROVIDERS = (process.env.NEXT_PUBLIC_AUTH_PROVIDERS ?? "").split(",").map((p) => p.trim());

type Props = { open: boolean; reason?: "guest_limit" | "nav"; onClose: () => void };

export function SignIn({ open, reason = "nav", onClose }: Props) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="scrim" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal aria-labelledby="signin-title" onClick={(e) => e.stopPropagation()}>
        <span className="px" style={{ color: "var(--red)", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, background: "var(--red)" }} />
          Box, box
        </span>
        <h2 id="signin-title">{reason === "guest_limit" ? "You've used your free questions." : "Sign in to Pitwall."}</h2>
        <p className="muted">Sign in to keep asking. It's free: 30 questions a day.</p>
        {PROVIDERS.includes("google") && (
          <button className="sso" onClick={() => signInWith("google")}>
            <img src="https://www.google.com/favicon.ico" width={18} height={18} alt="" />
            Continue with Google
          </button>
        )}
        {PROVIDERS.includes("github") && (
          <button className="sso" onClick={() => signInWith("github")}>
            <img src="https://github.com/favicon.ico" width={18} height={18} alt="" />
            Continue with GitHub
          </button>
        )}
        {PROVIDERS.some(Boolean) && (
          <div className="or px dim">
            <span />
            or
            <span />
          </div>
        )}
        {sent ? (
          <p className="sent">Check {email} for a sign-in link.</p>
        ) : (
          <form
            className="email"
            onSubmit={async (e) => {
              e.preventDefault();
              const result = await emailLink(email);
              if (result?.error) setError(result.error.message);
              else setSent(true);
            }}
          >
            <input type="email" required placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email" />
            <button className="send px">Email link</button>
          </form>
        )}
        {error && <p className="error">{error}</p>}
        <span className="dim" style={{ fontSize: 13 }}>
          Guests get a few questions a day per network. Your email is only used to sign you in.
        </span>
      </div>
    </div>
  );
}
