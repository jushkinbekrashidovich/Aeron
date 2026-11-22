# Manual checks (what the AI could not do)

The code, tests, builds and lint all pass, but nobody has yet opened the web app in a browser or built the Docker image. These two checklists close that gap. Tick the boxes as you go, and note anything that looks wrong (a screenshot helps) in an issue or send it to the AI to fix.

## A. Web app in a browser (about 20 minutes)

You need two terminals.

1. **Prepare once.** In the project folder: `source .venv/bin/activate`, then `python scripts/train_final.py --cutoff 2024-01-19 --tag replay` (about 5 seconds). This needs `data/processed/daily_us_embassy.csv`, which exists on your machine.
2. **Terminal 1, the API.** `uvicorn aeron.api.app:create_app --factory --port 8000`. Open http://localhost:8000/health in a browser: it should show `"status": "ok"`. Open http://localhost:8000/docs: the endpoints should be listed and "Try it out" on `/api/v1/forecast` with `origin=2024-12-22` should return three forecasts.
3. **Terminal 2, the web app.** `cd frontend`, `npm install` (if it fails with a cache permission error use `npm install --cache /tmp/npm-cache`), then `npm run dev`. Open http://localhost:3000.

What to look at:

- [ ] **Dashboard** (`/`): a yellow banner says it is a replay and not a current forecast. A date picker, "Previous day" and "Next day" buttons and four example buttons are visible. Three cards show "Predicted" and "Measured later" clearly separated, each with a coloured category label that also has words.
- [ ] Click each example. The cards change, the URL gets `?origin=...`, and "Clean day (25 May 2024)" shows low values with the "Good" or "Moderate" label.
- [ ] Type a date outside 21 Jan 2024 to 22 Feb 2025 (the picker should refuse it) and try the buttons at both ends of the range (they should be disabled).
- [ ] **Forecast** (`/forecast`): the chart shows a blue line (measured before), a purple diamond with a bar (predicted with 90% range) and a green dot (measured later) for three days. The two dashed lines are labelled 35.5 and 55.5. The table under it has the same numbers as the cards.
- [ ] **Research** (`/research`): text reads sensibly, the results table is present, and the "model serving this replay" box at the bottom fills in (version, training date).
- [ ] **Errors:** stop the API (Ctrl+C in terminal 1) and reload the page. You should see a plain message that the service could not be reached, not a blank page.
- [ ] **Phone layout:** in Chrome press F12, click the device icon and choose a phone size (for example 390 pixels wide). Cards should stack in one column, the chart should shrink without cutting off, and the table should scroll sideways.
- [ ] **Keyboard:** press Tab repeatedly from the top of the page. A "Skip to content" link appears first, then the menu, the date field and the buttons, each with a visible blue outline. Everything can be used without the mouse.
- [ ] **Screen reader (optional):** on a Mac turn on VoiceOver (Cmd+F5). The chart should be read as a described image, and table headers should be announced.
- [ ] **Speed:** in Chrome DevTools, open the Lighthouse tab and run a check on the Dashboard (Performance and Accessibility). Write the scores down; anything under 90 for accessibility is worth fixing.

Check the claims too: the Research page numbers should match `reports/model_evaluation/comparison.md`, `uncertainty.md` and `docs/research/live_data_decision.md`.

## B. First Docker build (about 15 minutes, needs Docker)

Docker is not installed on the machine where this was written, so the files have never run. If you have no Docker, install Docker Desktop (https://www.docker.com/products/docker-desktop/) and start it.

From the project folder:

1. `docker compose build` builds the image (a few minutes the first time). Expect that something small may need fixing on the first try. Send the error text to the AI.
2. `docker compose run --rm train` trains the replay model inside the image. It should print `saved /app/artifacts/models/...-replay-...`, and a new folder appears under `artifacts/models/` on your machine. (This step reads `data/processed/daily_us_embassy.csv`, which is mounted from your computer.)
3. `docker compose up api` starts the API. Open http://localhost:8000/health (should say `ok`) and http://localhost:8000/docs.
4. In another terminal run the web app as in section A (`npm run dev`) and check that it works against the container.
5. Stop with Ctrl+C, then `docker compose down`.

Also check:

- [ ] Without the data mounted, the API still starts and `/health` says `degraded` (this is what the CI container job checks): try `docker run --rm -p 8000:8000 aeron-api` and open /health.
- [ ] The container does not contain your data: `docker run --rm aeron-api ls /app/data/processed` should show an empty folder.

## C. Optional: a hosted demo

Only with the data owner's permission (see `docs/deployment.md`). Not needed for the project.
