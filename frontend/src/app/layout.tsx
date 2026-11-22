import type { Metadata } from "next";

import { Nav } from "@/components/Nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "AERON: PM2.5 forecast replay for Tashkent",
  description:
    "Replay of one-to-three-day PM2.5 forecasts for Tashkent, with prediction ranges, the model's limits and the research behind it.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900 antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-white focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <noscript>
          <p className="bg-red-50 px-4 py-3 text-red-950">
            This page needs JavaScript to load the forecasts. Turn it on in your browser and reload.
          </p>
        </noscript>
        <Nav />
        <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
