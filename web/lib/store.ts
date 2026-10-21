import type { Thread } from "./types";

const KEY = "pitwall.threads.v1";
const MAX_THREADS = 20;

/** Threads live in this browser only; every access can throw in private windows. */
export function loadThreads(): Thread[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function saveThreads(threads: Thread[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(threads.slice(0, MAX_THREADS)));
  } catch {
    // storage full or blocked: the session still works, it just is not kept
  }
}

export function loadTheme(): "light" | "dark" {
  try {
    return localStorage.getItem("pitwall.theme") === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function saveTheme(theme: "light" | "dark") {
  try {
    localStorage.setItem("pitwall.theme", theme);
  } catch {}
}
