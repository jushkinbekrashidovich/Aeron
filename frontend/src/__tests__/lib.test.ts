import { describe, expect, it } from "vitest";

import { ApiError, describeError } from "@/lib/api";
import { categoryFor, EPA_PM25_24H } from "@/lib/aqi";
import { buildScales, linePath, niceMax } from "@/lib/chart";
import { addDays, daysBetween, formatDate, isIsoDate } from "@/lib/dates";

describe("EPA PM2.5 categories (2024 revision)", () => {
  it.each([
    [0, "good"],
    [9.0, "good"],
    [9.1, "moderate"],
    [35.4, "moderate"],
    [35.5, "sensitive"],
    [55.4, "sensitive"],
    [55.5, "unhealthy"],
    [125.4, "unhealthy"],
    [125.5, "very-unhealthy"],
    [225.4, "very-unhealthy"],
    [225.5, "hazardous"],
    [900, "hazardous"],
  ])("%s is %s", (value, key) => {
    expect(categoryFor(value).key).toBe(key);
  });

  it("truncates to one decimal like EPA, so 55.49 is not yet unhealthy", () => {
    expect(categoryFor(55.49).key).toBe("sensitive");
    expect(categoryFor(-3).key).toBe("good");
  });

  it("has increasing lower limits", () => {
    const mins = EPA_PM25_24H.map((c) => c.min);
    expect([...mins].sort((a, b) => a - b)).toEqual(mins);
  });
});

describe("dates", () => {
  it("adds days across month and year ends", () => {
    expect(addDays("2024-12-31", 1)).toBe("2025-01-01");
    expect(addDays("2024-03-01", -1)).toBe("2024-02-29");
    expect(daysBetween("2024-12-22", "2025-01-01")).toBe(10);
  });
  it("validates ISO dates", () => {
    expect(isIsoDate("2025-01-26")).toBe(true);
    expect(isIsoDate("2025-02-30")).toBe(false);
    expect(isIsoDate("26/01/2025")).toBe(false);
  });
  it("formats", () => {
    expect(formatDate("2025-01-26")).toBe("26 Jan 2025");
  });
});

describe("chart geometry", () => {
  const forecasts = [
    {
      lead_days: 1,
      target_date: "2025-01-27",
      forecast: 80,
      interval_80: [50, 120],
      interval_90: [40, 150],
      probability_at_least_55_5: { conformal: 0.7, platt: 0.8 },
      probability_at_least_35_5: { conformal: 0.9, platt: 0.95 },
      persistence: 100,
      observed: 155,
      observed_inside_90: false,
      missing_input_share: 0,
    },
  ] as never;
  it("rounds axis ends up", () => {
    expect(niceMax(61)).toBe(75);
    expect(niceMax(130)).toBe(150);
  });
  it("places days left to right and larger values higher", () => {
    const s = buildScales("2025-01-26", 27, forecasts, []);
    expect(s.x("2025-01-27")).toBeGreaterThan(s.x("2025-01-26"));
    expect(s.y(100)).toBeLessThan(s.y(10));
    expect(s.yMax).toBeGreaterThanOrEqual(155);
  });
  it("breaks the line at a missing day", () => {
    const s = buildScales("2025-01-26", 27, [], []);
    const path = linePath(
      [
        { date: "2025-01-24", pm25_mean: 50 },
        { date: "2025-01-25", pm25_mean: null },
        { date: "2025-01-26", pm25_mean: 60 },
      ],
      s,
    );
    expect(path.match(/M/g)).toHaveLength(2);
    expect(path).not.toContain("L");
  });
});

describe("error messages", () => {
  it("explains the main failure cases in plain words", () => {
    expect(describeError(new ApiError(503, {}))).toMatch(/no data or model/);
    expect(describeError(new ApiError(404, {}))).toMatch(/not available for replay/);
    expect(describeError(new TypeError("fetch failed"))).toMatch(/could not be reached/);
  });
});
