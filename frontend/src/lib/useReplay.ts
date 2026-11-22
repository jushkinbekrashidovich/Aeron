"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  describeError,
  getForecast,
  getHistory,
  getRange,
  type ForecastResponse,
  type HistoryPoint,
  type ReplayRange,
} from "./api";
import { addDays, isIsoDate } from "./dates";

/** Days of observed history shown before the origin day. */
export const HISTORY_DAYS = 27;

/** Example days shown as shortcuts (all inside the replay range, checked against the API). */
export const PRESETS = [
  { date: "2024-12-22", label: "Polluted spell, forecast works" },
  { date: "2024-12-26", label: "Peak underpredicted" },
  { date: "2024-03-14", label: "Missed spike" },
  { date: "2024-05-25", label: "Clean day" },
];

type Loaded = {
  /** The origin day this data and error belong to, so stale results are never shown for another day. */
  origin: string;
  forecast: ForecastResponse | null;
  history: HistoryPoint[];
  error: string | null;
};

/** Loads the replay range, then the forecast and recent history for the origin day in the URL. */
export function useReplay() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const requested = params.get("origin");
  const [range, setRange] = useState<ReplayRange | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getRange(controller.signal)
      .then(setRange)
      .catch((e) => {
        if (!controller.signal.aborted) setRangeError(describeError(e));
      });
    return () => controller.abort();
  }, []);

  const origin =
    range === null
      ? null
      : requested && isIsoDate(requested)
        ? requested
        : PRESETS[0].date >= range.first_origin && PRESETS[0].date <= range.last_origin
          ? PRESETS[0].date
          : range.last_origin;

  useEffect(() => {
    if (origin === null) return;
    const controller = new AbortController();
    Promise.all([
      getForecast(origin, controller.signal),
      getHistory(addDays(origin, -HISTORY_DAYS), origin, controller.signal),
    ])
      .then(([forecast, history]) =>
        setLoaded({ origin, forecast, history: history.points, error: null }),
      )
      .catch((e) => {
        if (!controller.signal.aborted)
          setLoaded({ origin, forecast: null, history: [], error: describeError(e) });
      });
    return () => controller.abort();
  }, [origin]);

  const current = loaded !== null && loaded.origin === origin ? loaded : null;
  const setOrigin = useCallback(
    (date: string) => router.replace(`${pathname}?origin=${date}`, { scroll: false }),
    [router, pathname],
  );

  return {
    range,
    origin,
    forecast: current?.forecast ?? null,
    history: current?.history ?? [],
    loading: rangeError === null && (range === null || current === null),
    error: rangeError ?? current?.error ?? null,
    setOrigin,
  };
}
