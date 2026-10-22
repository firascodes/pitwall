"use client";

import Script from "next/script";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { LapReplay } from "@/components/LapReplay";

declare global {
  interface Window {
    Telegram?: { WebApp: { ready: () => void; expand: () => void; colorScheme: "light" | "dark" } };
  }
}

/** The Telegram Mini App: one replay, full width. /replay?laps=a,b&drivers=A,B&times=1:31.4,1:31.5 */
function Replay() {
  const params = useSearchParams();
  const list = (key: string) => (params.get(key) ?? "").split(",").filter(Boolean);
  const laps = list("laps");
  const data = { laps, drivers: list("drivers"), times: list("times"), ghost: laps.length > 1 };

  if (!laps.length) return <p style={{ padding: 16 }}>No lap given.</p>;
  return (
    <div style={{ padding: 12 }}>
      <LapReplay data={data} height={340} />
    </div>
  );
}

function telegramReady() {
  const app = window.Telegram?.WebApp;
  if (!app) return;
  app.ready();
  app.expand();
  document.documentElement.dataset.theme = app.colorScheme;
}

export default function ReplayPage() {
  return (
    <>
      <Script src="https://telegram.org/js/telegram-web-app.js" onReady={telegramReady} />
      <Suspense>
        <Replay />
      </Suspense>
    </>
  );
}
