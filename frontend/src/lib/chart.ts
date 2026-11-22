/** Geometry of the forecast chart. Pure functions, so they can be tested without a browser. */

import { addDays, daysBetween } from "./dates";
import type { HistoryPoint, LeadForecast } from "./api";

export const CHART = { width: 720, height: 340, left: 52, right: 16, top: 16, bottom: 44 };

export type Scales = {
  x: (date: string) => number;
  y: (value: number) => number;
  firstDay: string;
  lastDay: string;
  yMax: number;
  yTicks: number[];
};

/** Rounds a maximum up to a tidy axis end (50, 100, 150, 200, 250, ...). */
export function niceMax(value: number): number {
  const step = value <= 100 ? 25 : 50;
  return Math.max(step, Math.ceil(value / step) * step);
}

export function buildScales(origin: string, daysBack: number, forecasts: LeadForecast[], history: HistoryPoint[]): Scales {
  const firstDay = addDays(origin, -daysBack);
  const lastDay = addDays(origin, 3);
  const values = [
    ...history.map((p) => p.pm25_mean ?? 0),
    ...forecasts.flatMap((f) => [f.interval_90[1], f.observed ?? 0, f.persistence ?? 0]),
    60,
  ];
  const yMax = niceMax(Math.max(...values) * 1.05);
  const span = daysBetween(firstDay, lastDay);
  const innerW = CHART.width - CHART.left - CHART.right;
  const innerH = CHART.height - CHART.top - CHART.bottom;
  const step = yMax <= 100 ? 25 : 50;
  const yTicks: number[] = [];
  for (let v = 0; v <= yMax; v += step) yTicks.push(v);
  return {
    firstDay,
    lastDay,
    yMax,
    yTicks,
    x: (date) => CHART.left + (daysBetween(firstDay, date) / span) * innerW,
    y: (value) => CHART.top + innerH - (Math.min(value, yMax) / yMax) * innerH,
  };
}

/** SVG path of the observed series. A missing day breaks the line instead of being joined across. */
export function linePath(points: HistoryPoint[], scales: Scales): string {
  let path = "";
  let pen = false;
  for (const p of points) {
    if (p.pm25_mean === null) {
      pen = false;
      continue;
    }
    const x = scales.x(p.date).toFixed(1);
    const y = scales.y(p.pm25_mean).toFixed(1);
    path += `${pen ? "L" : "M"}${x},${y}`;
    pen = true;
  }
  return path;
}
