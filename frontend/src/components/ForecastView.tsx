"use client";

import { formatDate } from "@/lib/dates";
import { useReplay } from "@/lib/useReplay";

import { ForecastChart } from "./ForecastChart";
import { OriginPicker } from "./OriginPicker";
import { ReplayBanner } from "./ReplayBanner";

const num = (v: number | null) => (v === null ? "n/a" : v.toFixed(0));
const pct = (p: number) => `${Math.round(p * 100)}%`;

export function ForecastView() {
  const { range, origin, forecast, history, loading, error, setOrigin } = useReplay();
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Forecast</h1>
        <p className="mt-1 text-slate-800">
          Daily mean PM2.5 for the next three days, with a 90% range, the chance of reaching the alert level
          of 55.5 µg/m³, and a comparison with the simplest forecast: tomorrow equals today.
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
          <ForecastChart origin={origin} history={history} forecasts={forecast.forecasts} />
          <section aria-labelledby="table-title">
            <h2 id="table-title" className="mb-2 text-base font-semibold">
              Numbers for forecasts issued on {formatDate(origin)}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <caption className="sr-only">
                  Predicted and measured daily mean PM2.5 by forecast day, in micrograms per cubic metre
                </caption>
                <thead>
                  <tr className="border-b border-slate-400 text-left">
                    <th scope="col" className="py-2 pr-3">Day</th>
                    <th scope="col" className="py-2 pr-3">Predicted</th>
                    <th scope="col" className="py-2 pr-3">80% range</th>
                    <th scope="col" className="py-2 pr-3">90% range</th>
                    <th scope="col" className="py-2 pr-3">Chance ≥ 55.5</th>
                    <th scope="col" className="py-2 pr-3">Chance ≥ 35.5</th>
                    <th scope="col" className="py-2 pr-3">Measured later</th>
                    <th scope="col" className="py-2 pr-3">Error, model</th>
                    <th scope="col" className="py-2">Error, baseline</th>
                  </tr>
                </thead>
                <tbody>
                  {forecast.forecasts.map((f) => (
                    <tr key={f.lead_days} className="border-b border-slate-200">
                      <th scope="row" className="py-2 pr-3 text-left font-medium">
                        +{f.lead_days} ({formatDate(f.target_date)})
                      </th>
                      <td className="py-2 pr-3">{num(f.forecast)}</td>
                      <td className="py-2 pr-3">
                        {num(f.interval_80[0])} to {num(f.interval_80[1])}
                      </td>
                      <td className="py-2 pr-3">
                        {num(f.interval_90[0])} to {num(f.interval_90[1])}
                      </td>
                      <td className="py-2 pr-3">{pct(f.probability_at_least_55_5.conformal)}</td>
                      <td className="py-2 pr-3">{pct(f.probability_at_least_35_5.conformal)}</td>
                      <td className="py-2 pr-3">{num(f.observed)}</td>
                      <td className="py-2 pr-3">
                        {f.observed === null ? "n/a" : Math.abs(f.forecast - f.observed).toFixed(0)}
                      </td>
                      <td className="py-2">
                        {f.observed === null || f.persistence === null
                          ? "n/a"
                          : Math.abs(f.persistence - f.observed).toFixed(0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-slate-800">
              Error columns are absolute errors in µg/m³. The baseline is the daily mean of the day the
              forecast is issued. One day says little: over 137 winter days of this replay, the model&apos;s
              average error was 17.5, 21.7 and 21.2 µg/m³ at one, two and three days, against 24.4, 32.8 and
              35.7 for the baseline (see the Research page for sources and limits).
            </p>
            <p className="mt-2 text-xs text-slate-700">
              Model version {forecast.model_version}. Probabilities are the conformal version, the better
              calibrated of two computed with real weather forecasts.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
