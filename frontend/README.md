# AERON web app

Next.js (App Router), TypeScript and Tailwind. Three pages: Dashboard (`/`), Forecast (`/forecast`) and Research (`/research`). It shows a **replay** of past forecasts served by the API in `src/aeron/api/`; there is no current forecast.

```
npm install            # if this fails with a cache permission error: npm install --cache /tmp/npm-cache
npm run dev            # http://localhost:3000, expects the API at http://localhost:8000
npm test               # vitest: helpers and server-rendered components
npm run lint
npm run build
```

Set `NEXT_PUBLIC_API_URL` to use another API address. The API only accepts browser requests from `http://localhost:3000` unless `AERON_CORS_ORIGINS` is set.

Where things are: `src/lib/api.ts` (typed client), `src/lib/aqi.ts` (US EPA PM2.5 categories, 2024 revision), `src/lib/chart.ts` (chart geometry), `src/lib/useReplay.ts` (loading and the origin day in the URL), `src/components/` (pages' parts).

Every number on the Research and Forecast pages is copied from a report in `reports/model_evaluation/` or `docs/research/`. Change them together with the reports.
