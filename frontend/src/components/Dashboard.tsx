"use client";

import Link from "next/link";

import { formatDate } from "@/lib/dates";
import { STANDARD_NAME } from "@/lib/aqi";
import { useReplay } from "@/lib/useReplay";

import { AqiBadge } from "./AqiBadge";
import { LeadCard } from "./LeadCard";
import { OriginPicker } from "./OriginPicker";
import { ReplayBanner } from "./ReplayBanner";

export function Dashboard() {
  const { range, origin, forecast, history, loading, error, setOrigin } = useReplay();
  const measured = history.find((p) => p.date === origin)?.pm25_mean ?? null;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">PM2.5 in Tashkent: forecast replay</h1>
        <p className="mt-1 text-slate-800">
          Daily mean PM2.5 at the US Diplomatic Post monitor, forecast one to three days ahead. Pick a past
          day to see what the model predicted and what was measured.
        </p>
      </div>
      <ReplayBanner />
      {range && origin && <OriginPicker range={range} origin={origin} onChange={setOrigin} />}
      <div aria-live="polite">
        {loading && <p>Loading…</p>}
        {error && (
          <p role="alert" className="rounded border border-red-700 bg-red-50 px-4 py-3 text-red-950">
            {error}
          </p>
        )}
      </div>
      {forecast && origin && (
        <>
          <section aria-labelledby="measured-title" className="rounded-md border border-slate-300 bg-white p-4">
            <h2 id="measured-title" className="text-base font-semibold">
              Measured on {formatDate(origin)}, the day the forecast is issued
            </h2>
            {measured === null ? (
              <p>No daily mean was measured on this day.</p>
            ) : (
              <p className="mt-1 text-2xl font-semibold">
                {measured.toFixed(0)} <span className="text-base font-normal">µg/m³</span>{" "}
                <AqiBadge value={measured} />
              </p>
            )}
          </section>
          <section aria-labelledby="forecast-title">
            <h2 id="forecast-title" className="mb-2 text-base font-semibold">
              Forecast for the next three days
            </h2>
            <div className="grid gap-4 md:grid-cols-3">
              {forecast.forecasts.map((f) => (
                <LeadCard key={f.lead_days} f={f} />
              ))}
            </div>
            {forecast.problems.length > 0 && (
              <ul className="mt-3 list-disc pl-5 text-sm text-amber-900">
                {forecast.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-sm">
              <Link className="text-blue-800 underline" href={`/forecast?origin=${origin}`}>
                Chart, baseline comparison and details for this day
              </Link>
            </p>
          </section>
        </>
      )}
      <p className="text-sm text-slate-700">
        Categories: {STANDARD_NAME}. The 90% range is a prediction interval; in testing it held for about 85%
        of winter days, not 90% (see the Research page).
      </p>
    </div>
  );
}
