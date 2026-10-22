"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

/** Null when sign-in is not configured (local dev): everyone is a guest with no quota. */
export const supabase = url && key ? createClient(url, key) : null;

export function useSession(): Session | null {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);
  return session;
}

const back = () => `${window.location.origin}/chat`;

export const signInWith = (provider: "google" | "github") =>
  supabase?.auth.signInWithOAuth({ provider, options: { redirectTo: back() } });

export const emailLink = (email: string) =>
  supabase?.auth.signInWithOtp({ email, options: { emailRedirectTo: back() } });

export const signOut = () => supabase?.auth.signOut();
