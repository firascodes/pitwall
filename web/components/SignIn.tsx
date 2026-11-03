"use client";

import { useEffect, useState } from "react";
import { signIn, signInWith, signUp } from "@/lib/auth";

// Providers switched on in Supabase, e.g. NEXT_PUBLIC_AUTH_PROVIDERS=google,github
const PROVIDERS = (process.env.NEXT_PUBLIC_AUTH_PROVIDERS ?? "").split(",").map((p) => p.trim());

type Props = { open: boolean; reason?: "guest_limit" | "nav"; onClose: () => void };

export function SignIn({ open, reason = "nav", onClose }: Props) {
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, onClose]);

  if (!open) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const result = await (mode === "up" ? signUp(email, password) : signIn(email, password));
    if (result?.error) return setError(result.error.message);
    // With email confirmation on, a new account has no session until the link is opened
    if (mode === "up" && !result?.data.session) setSent(true);
    else onClose();
  }

  return (
    <div className="scrim" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal aria-labelledby="signin-title" onClick={(e) => e.stopPropagation()}>
        <span className="px" style={{ color: "var(--red)", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, background: "var(--red)" }} />
          Box, box
        </span>
        <h2 id="signin-title">{reason === "guest_limit" ? "You've used your free questions." : (mode === "up" ? "Create your account." : "Sign in to Pitwall.")}</h2>
        <p className="muted">Sign in to keep asking. It's free: 30 questions a day.</p>
        {(["google", "github"] as const).map((p) => (
          <button key={p} className="sso" disabled={!PROVIDERS.includes(p)} onClick={() => signInWith(p)}>
            <img src={p === "google" ? "https://www.google.com/favicon.ico" : "https://github.com/favicon.ico"} width={18} height={18} alt="" />
            Continue with {p === "google" ? "Google" : "GitHub"}
            {!PROVIDERS.includes(p) && <span className="soon px">Soon</span>}
          </button>
        ))}
        <div className="or px dim">
          <span />
          or
          <span />
        </div>
        {sent ? (
          <p className="sent">Check {email} for a link to confirm your account, then sign in.</p>
        ) : (
          <form className="credentials" onSubmit={submit}>
            <input type="email" required placeholder="you@example.com" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email" />
            <input
              type="password"
              required
              minLength={8}
              placeholder="Password (8+ characters)"
              autoComplete={mode === "up" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-label="Password"
            />
            <button className="send px">{mode === "up" ? "Create account" : "Sign in"}</button>
            <button type="button" className="switch" onClick={() => setMode(mode === "up" ? "in" : "up")}>
              {mode === "up" ? "Have an account? Sign in" : "New here? Create an account"}
            </button>
          </form>
        )}
        {error && <p className="error">{error}</p>}
        <span className="dim" style={{ fontSize: 13 }}>
          Guests get a few questions a day per network. Your email and password are stored by Supabase Auth, never by Pitwall.
        </span>
      </div>
    </div>
  );
}
