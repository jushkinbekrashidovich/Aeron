import type { LeadForecast } from "@/lib/api";
import { formatDate } from "@/lib/dates";

import { AqiBadge } from "./AqiBadge";

const pct = (p: number) => `${Math.round(p * 100)}%`;
const num = (v: number) => v.toFixed(0);

/** One forecast day: predicted value and range, and (in a replay) what was measured later. */
export function LeadCard({ f }: { f: LeadForecast }) {
  const outcome =
    f.observed === null
      ? "No measurement for this day."
      : f.observed_inside_90
        ? "Inside the 90% range."
        : f.observed > f.interval_90[1]
          ? "Above the 90% range."
          : "Below the 90% range.";
  return (
    <article
      aria-label={`Forecast ${f.lead_days} day${f.lead_days > 1 ? "s" : ""} ahead`}
      className="rounded-md border border-slate-300 bg-white p-4"
    >
      <h3 className="text-sm font-semibold text-slate-700">
        {f.lead_days} day{f.lead_days > 1 ? "s" : ""} ahead: {formatDate(f.target_date)}
      </h3>
      <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-blue-800">Predicted</p>
      <p className="text-3xl font-semibold">
        {num(f.forecast)} <span className="text-base font-normal">µg/m³</span>
      </p>
      <div className="mt-1">
        <AqiBadge value={f.forecast} />
      </div>
      <dl className="mt-3 space-y-1 text-sm">
        <div className="flex justify-between gap-2">
          <dt>90% range</dt>
          <dd>
            {num(f.interval_90[0])} to {num(f.interval_90[1])} µg/m³
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Chance of 55.5 or more</dt>
          <dd>{pct(f.probability_at_least_55_5.conformal)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Baseline: same as day issued</dt>
          <dd>{f.persistence === null ? "n/a" : `${num(f.persistence)} µg/m³`}</dd>
        </div>
      </dl>
      <div className="mt-3 border-t border-slate-200 pt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-900">Measured later</p>
        {f.observed === null ? (
          <p className="text-sm">{outcome}</p>
        ) : (
          <>
            <p className="text-xl font-semibold">
              {num(f.observed)} <span className="text-sm font-normal">µg/m³</span>
            </p>
            <div className="mt-1">
              <AqiBadge value={f.observed} />
            </div>
            <p className="mt-1 text-sm">{outcome}</p>
          </>
        )}
      </div>
    </article>
  );
}
