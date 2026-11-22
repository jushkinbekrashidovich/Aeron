import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AqiBadge } from "@/components/AqiBadge";
import { ForecastChart } from "@/components/ForecastChart";
import { LeadCard } from "@/components/LeadCard";
import { ReplayBanner } from "@/components/ReplayBanner";
import type { LeadForecast } from "@/lib/api";

const base: LeadForecast = {
  lead_days: 1,
  target_date: "2025-01-27",
  forecast: 85.9,
  interval_80: [55, 130],
  interval_90: [47.1, 158.3],
  probability_at_least_55_5: { conformal: 0.869, platt: 0.95 },
  probability_at_least_35_5: { conformal: 0.97, platt: 0.99 },
  persistence: 105.1,
  observed: 155.7,
  observed_inside_90: true,
  missing_input_share: 0,
};

describe("LeadCard", () => {
  it("labels predicted and measured values separately", () => {
    const html = renderToStaticMarkup(<LeadCard f={base} />);
    expect(html).toContain("Predicted");
    expect(html).toContain("Measured later");
    expect(html).toContain("86"); // forecast
    expect(html).toContain("156"); // observed
    expect(html).toContain("87%"); // chance of 55.5 or more
    expect(html).toContain("Inside the 90% range.");
  });

  it("says when the measurement fell outside the range", () => {
    const html = renderToStaticMarkup(<LeadCard f={{ ...base, observed: 200, observed_inside_90: false }} />);
    expect(html).toContain("Above the 90% range.");
  });

  it("handles a missing measurement", () => {
    const html = renderToStaticMarkup(<LeadCard f={{ ...base, observed: null, observed_inside_90: null }} />);
    expect(html).toContain("No measurement for this day.");
  });

  it("uses the category text, not only colour", () => {
    expect(renderToStaticMarkup(<AqiBadge value={85.9} />)).toContain("Unhealthy");
  });
});

describe("ReplayBanner", () => {
  it("states plainly that this is not a current forecast", () => {
    const html = renderToStaticMarkup(<ReplayBanner />);
    expect(html).toContain("Replay of historical data");
    expect(html).toContain("not a current forecast");
  });
});

describe("ForecastChart", () => {
  it("is described for screen readers and shows the forecast, range and outcome", () => {
    const html = renderToStaticMarkup(
      <ForecastChart
        origin="2025-01-26"
        history={[
          { date: "2025-01-25", pm25_mean: 90 },
          { date: "2025-01-26", pm25_mean: 105.1 },
        ]}
        forecasts={[base]}
      />,
    );
    expect(html).toContain('role="img"');
    expect(html).toContain("aria-label");
    expect(html).toContain("forecast issued");
    expect(html).toContain("Green dot");
  });
});
