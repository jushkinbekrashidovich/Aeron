"use client";

import { addDays, formatDate, isIsoDate } from "@/lib/dates";
import type { ReplayRange } from "@/lib/api";
import { PRESETS } from "@/lib/useReplay";

type Props = {
  range: ReplayRange;
  origin: string;
  onChange: (date: string) => void;
};

/** Chooses the origin day, the day on which the forecast is issued. */
export function OriginPicker({ range, origin, onChange }: Props) {
  const inRange = (d: string) => d >= range.first_origin && d <= range.last_origin;
  const step = (days: number) => {
    const next = addDays(origin, days);
    if (inRange(next)) onChange(next);
  };
  return (
    <section aria-labelledby="picker-title" className="rounded-md border border-slate-300 bg-white p-4">
      <h2 id="picker-title" className="text-base font-semibold">
        Choose the day the forecast is issued
      </h2>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="origin" className="block text-sm font-medium">
            Forecast issued at the end of
          </label>
          <input
            id="origin"
            type="date"
            value={origin}
            min={range.first_origin}
            max={range.last_origin}
            onChange={(e) => {
              if (isIsoDate(e.target.value) && inRange(e.target.value)) onChange(e.target.value);
            }}
            className="mt-1 rounded border border-slate-400 px-2 py-1"
          />
        </div>
        <button
          type="button"
          onClick={() => step(-1)}
          disabled={!inRange(addDays(origin, -1))}
          className="rounded border border-slate-400 px-3 py-1 text-sm disabled:opacity-40"
        >
          Previous day
        </button>
        <button
          type="button"
          onClick={() => step(1)}
          disabled={!inRange(addDays(origin, 1))}
          className="rounded border border-slate-400 px-3 py-1 text-sm disabled:opacity-40"
        >
          Next day
        </button>
      </div>
      <p className="mt-2 text-sm text-slate-700">
        Available: {formatDate(range.first_origin)} to {formatDate(range.last_origin)} ({range.origins} days
        with measurements for the following three days).
      </p>
      <div className="mt-3 flex flex-wrap gap-2" aria-label="Example days">
        {PRESETS.filter((p) => inRange(p.date)).map((p) => (
          <button
            key={p.date}
            type="button"
            onClick={() => onChange(p.date)}
            aria-pressed={p.date === origin}
            className="rounded-full border border-slate-400 px-3 py-1 text-sm aria-pressed:bg-slate-900 aria-pressed:text-white"
          >
            {p.label} ({formatDate(p.date)})
          </button>
        ))}
      </div>
    </section>
  );
}
