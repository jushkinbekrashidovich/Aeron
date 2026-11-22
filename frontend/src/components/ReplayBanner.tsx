/** Shown on every page that has forecasts: these are replays, not current forecasts. */
export function ReplayBanner() {
  return (
    <div
      role="note"
      className="rounded-md border border-amber-600 bg-amber-50 px-4 py-3 text-sm text-amber-950"
    >
      <strong>Replay of historical data.</strong> Each forecast shows what the model would have predicted
      on the chosen day, using only information available then. The measured PM2.5 series ends on 25
      February 2025, so this is not a current forecast and must not be used to plan today.
    </div>
  );
}
