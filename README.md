# Roam — local-powered travel

A responsive Kochi travel app with a React/JavaScript interface, Python/FastAPI API and persistent SQLite database. Built in `work/`.

## What works

- Browse and search eight seeded itinerary collections across twelve Kochi hubs; filter by area, interests or aggregate SLH.
- Save collections to your guest session.
- Generate and save 1–3 day trips with selected Kochi areas, budget, interests, pace, dates, opening-window constraints, clustered travel estimates and budget utilization.
- View day timelines and OpenStreetMap pins; launch external walking or transit directions.
- Replace or remove stops and recalculate schedule and costs before starting progress.
- Mark stops complete, undo mistakes, persist progress, earn points and badges without duplicate rewards.
- Inspect Safety, Legitimacy and Hygiene scores, dimensions, review count, date and methodology. Trip scores derive from their stops.
- Save travel stories, review catalog-matched places, edit drafts and turn them into scheduled trips.
- Opt into optional Gemini extraction when a backend Google AI key is configured; failures preserve the original story with an explicitly labeled fallback.
- Try persistent, explicitly demo-only group join/withdraw requests.
- Keyboard-friendly controls, focus-managed SLH dialogs, responsive layouts and reduced-motion styles.

## Run locally (Windows PowerShell)

Requires Node 22+ and Python 3.12+.

```powershell
cd work
npm ci
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
npm run start:local
```

Open **http://127.0.0.1:5173/**. API documentation: **http://127.0.0.1:8000/docs**.

For separate development terminals:

```powershell
# Terminal 1, in work/
.\.venv\Scripts\python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
# Terminal 2, in work/
npm run dev
```

On macOS/Linux use `.venv/bin/python` instead. The combined start script handles both paths automatically. Stop existing servers before starting another instance; the frontend intentionally uses strict port 5173.

## Optional AI

Copy `work/.env.example` to `work/.env`, fill `GEMINI_API_KEY` locally and optionally set `GEMINI_MODEL`. The combined start command loads this file. For separate terminals, export these variables in the Python terminal. Restart the backend after changes.

The contribution form then offers an explicit opt-in checkbox. Only submitted story text and the public place catalog are sent to Google. Keys never reach the frontend. The adapter uses the [Gemini Interactions API structured-output format](https://ai.google.dev/gemini-api/docs/structured-output?lang=rest), validates returned IDs against the catalog and retains a local fallback. A live paid API request has not been exercised in this build.

## Deploy on Render

The root `render.yaml` and multi-stage `Dockerfile` deploy the React build and FastAPI API as one same-origin web service. Open the [Render Blueprint](https://dashboard.render.com/blueprint/new?repo=https://github.com/abhiramps8921/sih2026), connect the repository and apply the `roam-kochi` service. The health check is `/api/health`.

The app works without an AI key using its seeded catalog and deterministic planner. To enable story extraction, add `GEMINI_API_KEY` in the Render service's Environment page; `GEMINI_MODEL` is optional.

The free Render service stores SQLite data on an ephemeral filesystem, so guest trips, drafts and progress can reset after a restart or deploy. A durable production setup should attach a persistent disk on a paid instance or move the same data model to a managed database.

## Data and scope

`work/backend/roam.db` is created on first start and excluded from Git. Guest ownership is based on an HttpOnly, SameSite cookie; clearing that cookie loses access to that session’s data. This is pilot-grade guest isolation rather than production authentication. Bind manual development servers to loopback; the Render image exposes only the public application port.

The venue hours, costs, review counts, SLH ratings and contributor identities are **sample data**, not live or verified information. Some meal stops represent suggested experiences rather than verified businesses. Routes are approximate walking or local-transit estimates with schematic connecting lines, not road routing. Food and local transport have a separate ₹400 daily allowance. Stay and travel to Kochi are excluded.

Premium dining examples are based on the official venue listings for [Kochi Kitchen](https://www.marriott.com/en-us/hotels/cokmc-kochi-marriott-hotel/dining/), [All Spice](https://www.marriott.com/en-us/dining/restaurant-bar/cokic-courtyard-kochi-infopark/7259411-all-spice.mi) and [SkyGrill](https://www.ihg.com/crowneplaza/hotels/gb/en/kochi/cokch/hoteldetail/dining). Their seeded prices remain illustrative and must be confirmed with the venue.

SLH = `(Safety + Legitimacy + Hygiene) / 15 × 100`, with each dimension rated 1–5. Legitimacy is scam resistance: a higher L score means a lower likelihood of misleading listings, hidden charges or untrustworthy operators. Missing or invalid dimensions result in no rating. An itinerary’s score averages its stop dimensions equally. No score certifies safety. No actual reviews are collected yet.

Story publishing, live stranger matching/chat, verified accounts, moderation, multi-city scale and real routing-provider integration remain beyond this local MVP. Community requests contact nobody. Native Android/iOS packaging is not included; this deliverable is the responsive web application.

## Checks

```powershell
cd work
npm test
npm run build
npm run format:check
.\.venv\Scripts\python -m pytest backend/test_api.py -q
```

Backend tests cover schedules, constraints, ownership, persistence, idempotent completion, rewards, bookmarks, editing, story extraction fallback and draft-to-trip conversion. Frontend tests cover SLH calculations and aggregation. GitHub Actions runs tests, formatting and the production build on pushes and pull requests.

All five requested skills are installed under `.agents/skills/`. Photo credits and licenses are available inside the app at `/credits`.
