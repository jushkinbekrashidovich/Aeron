/** Typed client of the AERON replay API (see src/aeron/api/schemas.py). */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Probabilities = { conformal: number; platt: number };

export type LeadForecast = {
  lead_days: number;
  target_date: string;
  forecast: number;
  interval_80: [number, number];
  interval_90: [number, number];
  probability_at_least_55_5: Probabilities;
  probability_at_least_35_5: Probabilities;
  persistence: number | null;
  observed: number | null;
  observed_inside_90: boolean | null;
  missing_input_share: number;
};

export type ForecastResponse = {
  mode: "replay";
  notice: string;
  origin_date: string;
  model_version: string;
  forecasts: LeadForecast[];
  problems: string[];
};

export type ReplayRange = {
  mode: "replay";
  notice: string;
  first_origin: string;
  last_origin: string;
  origins: number;
};

export type HistoryPoint = { date: string; pm25_mean: number | null };
export type HistoryResponse = { unit: string; start: string; end: string; points: HistoryPoint[] };

export type ModelCard = {
  version: string;
  model: string;
  feature_set: string;
  target: string;
  leads_days: number[];
  training_cutoff: string | null;
  last_training_target_date: string;
  built_utc: string;
  git_commit: string;
  known_limits: string[];
  per_lead: Record<string, { training_rows: number; calibration_rows: number; n_inputs: number }>;
  evaluation?: {
    winter_test_error: Record<string, Record<string, { n: number; mae: number; rmse: number; bias: number }>>;
    source: string;
  };
};

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

/** How long to wait for the API before giving up and saying so. */
export const TIMEOUT_MS = 15_000;

export class TimeoutError extends Error {
  constructor() {
    super("timeout");
  }
}

async function get<T>(path: string, params: Record<string, string> = {}, signal?: AbortSignal): Promise<T> {
  const url = new URL(path, API_URL);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const own = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    own.abort();
  }, TIMEOUT_MS);
  const relay = () => own.abort();
  signal?.addEventListener("abort", relay);
  try {
    const response = await fetch(url, { signal: own.signal });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(response.status, body?.detail ?? body);
    return body as T;
  } catch (error) {
    if (timedOut) throw new TimeoutError();
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", relay);
  }
}

export const getRange = (signal?: AbortSignal) => get<ReplayRange>("/api/v1/replay/range", {}, signal);
export const getForecast = (origin: string, signal?: AbortSignal) =>
  get<ForecastResponse>("/api/v1/forecast", { origin }, signal);
export const getHistory = (start: string, end: string, signal?: AbortSignal) =>
  get<HistoryResponse>("/api/v1/history", { start, end }, signal);
export const getModel = (signal?: AbortSignal) => get<ModelCard>("/api/v1/model", {}, signal);

/** A short message for the user from a failed request. */
export function describeError(error: unknown): string {
  if (error instanceof TimeoutError)
    return `The service at ${API_URL} did not answer within ${TIMEOUT_MS / 1000} seconds. Check that the API is running.`;
  if (error instanceof ApiError) {
    if (error.status === 503) return "The service is running but has no data or model loaded yet.";
    if (error.status === 404) return "That day is not available for replay.";
    return `The service refused the request (${error.status}).`;
  }
  return `The service at ${API_URL} could not be reached. Check that the API is running, and that this page is opened as http://localhost:3000.`;
}
