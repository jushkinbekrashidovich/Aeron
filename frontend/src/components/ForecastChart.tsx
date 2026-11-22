import type { HistoryPoint, LeadForecast } from "@/lib/api";
import { addDays, formatDate, formatShort } from "@/lib/dates";
import { buildScales, CHART, linePath } from "@/lib/chart";

type Props = {
  origin: string;
  history: HistoryPoint[];
  forecasts: LeadForecast[];
  daysBack?: number;
};

const REFERENCE_LEVELS = [
  { value: 35.5, label: "35.5: unhealthy for sensitive groups starts" },
  { value: 55.5, label: "55.5: unhealthy starts (alert level)" },
];

/** Observed daily means up to the origin day, the forecast with its 90% range, and what was measured later. */
export function ForecastChart({ origin, history, forecasts, daysBack = 27 }: Props) {
  const s = buildScales(origin, daysBack, forecasts, history);
  const bottom = CHART.height - CHART.bottom;
  const ticks: string[] = [];
  for (let d = s.firstDay; d <= s.lastDay; d = addDays(d, 7)) ticks.push(d);
  const label = `Daily mean PM2.5 from ${formatDate(s.firstDay)} to ${formatDate(origin)}, with forecasts for the next three days and the values measured later.`;
  return (
    <figure>
      <svg
        viewBox={`0 0 ${CHART.width} ${CHART.height}`}
        role="img"
        aria-label={label}
        className="h-auto w-full rounded-md border border-slate-300 bg-white"
      >
        {s.yTicks.map((v) => (
          <g key={v}>
            <line x1={CHART.left} x2={CHART.width - CHART.right} y1={s.y(v)} y2={s.y(v)} stroke="#e2e8f0" />
            <text x={CHART.left - 8} y={s.y(v) + 4} textAnchor="end" fontSize="11" fill="#334155">
              {v}
            </text>
          </g>
        ))}
        <text transform={`translate(14 ${(CHART.top + bottom) / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fill="#334155">
          PM2.5 daily mean (µg/m³)
        </text>
        {REFERENCE_LEVELS.map((r) => (
          <g key={r.value}>
            <line
              x1={CHART.left}
              x2={CHART.width - CHART.right}
              y1={s.y(r.value)}
              y2={s.y(r.value)}
              stroke="#b45309"
              strokeDasharray="4 3"
            />
            <text x={CHART.left + 4} y={s.y(r.value) - 3} fontSize="10" fill="#92400e">
              {r.label}
            </text>
          </g>
        ))}
        {ticks.map((d) => (
          <text key={d} x={s.x(d)} y={bottom + 16} textAnchor="middle" fontSize="11" fill="#334155">
            {formatShort(d)}
          </text>
        ))}
        <line x1={s.x(origin)} x2={s.x(origin)} y1={CHART.top} y2={bottom} stroke="#475569" strokeDasharray="2 3" />
        <text x={s.x(origin) - 4} y={CHART.top + 10} textAnchor="end" fontSize="10" fill="#334155">
          forecast issued
        </text>
        <path d={linePath(history, s)} fill="none" stroke="#1d4ed8" strokeWidth="2" />
        {history.map(
          (p) =>
            p.pm25_mean !== null && <circle key={p.date} cx={s.x(p.date)} cy={s.y(p.pm25_mean)} r="2.5" fill="#1d4ed8" />,
        )}
        {forecasts.map((f) => {
          const x = s.x(f.target_date);
          return (
            <g key={f.lead_days}>
              <line x1={x} x2={x} y1={s.y(f.interval_90[0])} y2={s.y(f.interval_90[1])} stroke="#7c3aed" strokeWidth="2" />
              <line x1={x - 5} x2={x + 5} y1={s.y(f.interval_90[0])} y2={s.y(f.interval_90[0])} stroke="#7c3aed" strokeWidth="2" />
              <line x1={x - 5} x2={x + 5} y1={s.y(f.interval_90[1])} y2={s.y(f.interval_90[1])} stroke="#7c3aed" strokeWidth="2" />
              <path
                d={`M${x},${s.y(f.forecast) - 6} L${x + 6},${s.y(f.forecast)} L${x},${s.y(f.forecast) + 6} L${x - 6},${s.y(f.forecast)} Z`}
                fill="#7c3aed"
              />
              {f.observed !== null && (
                <circle cx={x + 10} cy={s.y(f.observed)} r="4.5" fill="#047857" stroke="#ffffff" strokeWidth="1.5" />
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-800">
        <span>
          <span className="font-semibold text-blue-700">Blue line</span>: measured before the forecast
        </span>
        <span>
          <span className="font-semibold text-violet-700">Diamond and bar</span>: predicted value and 90% range
        </span>
        <span>
          <span className="font-semibold text-emerald-700">Green dot</span>: measured later
        </span>
      </figcaption>
    </figure>
  );
}
