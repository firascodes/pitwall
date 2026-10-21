import type { Metadata, Viewport } from "next";
import { JetBrains_Mono, Silkscreen, Titillium_Web } from "next/font/google";
import "./globals.css";

const pixel = Silkscreen({ weight: "400", subsets: ["latin"], variable: "--font-px" });
const body = Titillium_Web({
  weight: ["400", "600", "700", "900"],
  subsets: ["latin"],
  variable: "--font-body",
});
const mono = JetBrains_Mono({ weight: ["400", "600"], subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Pitwall",
  description: "An F1 2026 race engineer built on a Neo4j knowledge graph and real telemetry.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Set the saved theme before paint, so a dark-mode reload does not flash white
const themeScript = `try{document.documentElement.dataset.theme=localStorage.getItem("pitwall.theme")==="dark"?"dark":"light"}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={`${pixel.variable} ${body.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}
