import { Suspense } from "react";

import { ForecastView } from "@/components/ForecastView";

export const metadata = { title: "Forecast | AERON" };

export default function ForecastPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <ForecastView />
    </Suspense>
  );
}
