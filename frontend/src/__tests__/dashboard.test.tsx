// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(""),
}));

import { Dashboard } from "@/components/Dashboard";

const range = {
  mode: "replay",
  notice: "x",
  first_origin: "2024-01-21",
  last_origin: "2025-02-22",
  origins: 340,
};
const lead = (n: number, date: string) => ({
  lead_days: n,
  target_date: date,
  forecast: 98.4,
  interval_80: [60, 150],
  interval_90: [54, 180],
  probability_at_least_55_5: { conformal: 0.94, platt: 0.99 },
  probability_at_least_35_5: { conformal: 0.98, platt: 0.99 },
  persistence: 71.8,
  observed: 116.8,
  observed_inside_90: true,
  missing_input_share: 0,
});
const forecast = {
  mode: "replay",
  notice: "x",
  origin_date: "2024-12-22",
  model_version: "test",
  forecasts: [lead(1, "2024-12-23"), lead(2, "2024-12-24"), lead(3, "2024-12-25")],
  problems: [],
};
const history = {
  unit: "ug/m3",
  start: "2024-11-25",
  end: "2024-12-22",
  points: [
    { date: "2024-12-21", pm25_mean: 44.0 },
    { date: "2024-12-22", pm25_mean: 71.8 },
  ],
};

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("Dashboard in a browser-like environment", () => {
  it("goes from Loading to the forecast cards when the API answers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: URL) => {
        const path = String(url);
        if (path.includes("/replay/range")) return json(range);
        if (path.includes("/forecast")) return json(forecast);
        if (path.includes("/history")) return json(history);
        return json({}, 404);
      }),
    );
    render(<Dashboard />);
    expect(screen.getByText("Loading…")).toBeTruthy();
    await waitFor(() => expect(screen.getAllByText("Predicted").length).toBe(3));
    expect(screen.queryByText("Loading…")).toBeNull();
    expect(screen.getAllByText("Measured later").length).toBe(3);
  });

  it("shows an error naming the API address when the API cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    render(<Dashboard />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/localhost:8000/);
    expect(screen.queryByText("Loading…")).toBeNull();
  });

  it("shows an error when the API answers 503", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ detail: { error: "service not ready" } }, 503)));
    render(<Dashboard />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/no data or model/);
  });

  it("gives up with a message when the API never answers", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: URL, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
      ),
    );
    render(<Dashboard />);
    await vi.advanceTimersByTimeAsync(16_000);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/did not answer/);
  });
});
