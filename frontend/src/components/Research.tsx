import { ModelCardPanel } from "./ModelCardPanel";
import { ReplayBanner } from "./ReplayBanner";

/**
 * Every number on this page comes from a report in the repository (named next to it).
 * Update them together with the reports; they are checked in the honesty review (task 6.3.3).
 */
export function Research() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Research notes</h1>
        <p className="mt-1 text-slate-800">
          What was built, how it was tested, what the numbers are, and where it falls short.
        </p>
      </div>
      <ReplayBanner />

      <section aria-labelledby="q" className="space-y-2">
        <h2 id="q" className="text-lg font-semibold">The question</h2>
        <p>
          How well can the daily mean PM2.5 at one monitor in Tashkent be forecast one, two and three days
          ahead, and how reliable are the stated uncertainty and the chance of exceeding 55.5 µg/m³? The
          forecast is issued at the end of each local day (UTC+5).
        </p>
      </section>

      <section aria-labelledby="data" className="space-y-2">
        <h2 id="data" className="text-lg font-semibold">Data</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            PM2.5 from the US Diplomatic Post monitor, hourly, from November 2018 to 25 February 2025
            (OpenAQ, location 8881). It is the only station with several years of data. Nothing here
            describes other parts of the city.
          </li>
          <li>
            Weather from ERA5 reanalysis, and archived weather forecasts from 19 January 2024 onwards.
            Models are trained on observed weather and tested on the forecasts that existed at the time.
          </li>
          <li>
            Gaps are not filled. 1,823 days have a daily mean (at least 18 valid hours).
          </li>
        </ul>
      </section>

      <section aria-labelledby="method" className="space-y-2">
        <h2 id="method" className="text-lg font-semibold">Method</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Test design: models are refitted before each season (winters and March to October) and tested
            on the following season, never on days they were trained on, with a gap equal to the forecast
            lead.
          </li>
          <li>
            Chosen model: LightGBM with PM2.5 history, calendar, observed weather up to the issue day and
            the archived weather forecast for the target day. It was chosen by the project owner; ridge
            regression, random forest and XGBoost were within about 1 to 2 µg/m³ of it.
          </li>
          <li>
            Ranges: split-conformal prediction intervals, scaled to the forecast level. Probabilities:
            from the same calibration errors.
          </li>
        </ul>
      </section>

      <section aria-labelledby="results" className="space-y-3">
        <h2 id="results" className="text-lg font-semibold">Results</h2>
        <p>
          Average absolute error (µg/m³) on winter days, tested with real archived forecasts (about 140
          days from two winters). Source: <code>reports/model_evaluation/comparison.md</code>.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] border-collapse text-sm">
            <caption className="sr-only">Winter average absolute error by model and forecast lead</caption>
            <thead>
              <tr className="border-b border-slate-400 text-left">
                <th scope="col" className="py-2 pr-3">Model</th>
                <th scope="col" className="py-2 pr-3">1 day</th>
                <th scope="col" className="py-2 pr-3">2 days</th>
                <th scope="col" className="py-2">3 days</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Tomorrow equals today", "24.1", "32.4", "35.1"],
                ["Typical value for the time of year", "25.9", "25.7", "25.8"],
                ["Ridge regression with forecast weather", "18.2", "22.4", "23.6"],
                ["LightGBM with forecast weather (chosen)", "17.1", "20.9", "22.0"],
              ].map((r) => (
                <tr key={r[0]} className="border-b border-slate-200">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">{r[0]}</th>
                  <td className="py-2 pr-3">{r[1]}</td>
                  <td className="py-2 pr-3">{r[2]}</td>
                  <td className="py-2">{r[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Weather inputs reduce the winter error by about 2 to 7 µg/m³. Choosing between the models
            matters much less: with real forecasts, no tree model was reliably better than ridge
            regression.
          </li>
          <li>
            In March to October 2024 the weather-based models did worse than the history-only models with
            real forecasts, and the simple baseline beat every model that used forecast wind.
          </li>
          <li>
            The 90% range contained the measured value on 80% to 86% of winter days when tested with
            perfect-forecast weather, and on 87% to 93% with real forecasts. In the replay on this site it
            was 84% to 85%. Source: <code>reports/model_evaluation/uncertainty.md</code>.
          </li>
          <li>
            The highest days are underpredicted. Winter days at or above 100 µg/m³ were forecast too low by
            24 to 59 µg/m³ on average, although the forecast reached the alert level of 55.5 on most of
            them (80% to 100%). Source: <code>reports/model_evaluation/error_analysis.md</code>.
          </li>
          <li>
            For the next day the model relies most on the PM2.5 of the day the forecast is issued (its
            evening mean and its daily mean) and on forecast wind. For later days forecast wind, gusts,
            the 14-day mean, pressure and rain count most. These are associations the model learned, not
            causes.
            Source: <code>reports/model_evaluation/explainability.md</code>.
          </li>
        </ul>
      </section>

      <section aria-labelledby="limits" className="space-y-2">
        <h2 id="limits" className="text-lg font-semibold">Limitations</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>One station, five winters of testing, and only about 140 winter days with real weather forecasts.</li>
          <li>The measured series ends in February 2025, so there is no current forecast. This site replays the past.</li>
          <li>
            Intervals fell short of their nominal 90% in winter, misses come in runs of days, and the ranges
            are wide (60 to 130 µg/m³ for a winter day).
          </li>
          <li>Probabilities computed from real forecasts can be overconfident (the Platt version more than the conformal version used here).</li>
          <li>
            Not done: hourly forecasts, deep learning, interpolation between stations, a live data feed, and
            hosted deployment. The full list is in <code>docs/research/limitations.md</code>.
          </li>
        </ul>
      </section>

      <section aria-labelledby="card" className="space-y-2">
        <h2 id="card" className="text-lg font-semibold">The model serving this replay</h2>
        <ModelCardPanel />
      </section>
    </div>
  );
}
