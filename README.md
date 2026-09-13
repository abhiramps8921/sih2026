# Roam — local-powered travel

A responsive Kochi travel app with a React/JavaScript interface, Python/FastAPI API and persistent SQLite database. Built in `work/`.

## What works

- Browse and search four seeded itinerary collections; filter by interests or aggregate SLH.
- Save collections to your guest session.
- Generate and save 1–3 day trips with budget, interests, pace, dates, opening-window constraints, travel estimates and buffers.
- View day timelines and OpenStreetMap pins; launch external walking directions.
- Replace or remove stops and recalculate schedule and costs before starting progress.
- Mark stops complete, undo mistakes, persist progress, earn points and badges without duplicate rewards.
- Inspect Safety, Legitimacy and Hygiene scores, dimensions, review count, date and methodology. Trip scores derive from their stops.
- Save travel stories, review catalog-matched places, edit drafts and turn them into scheduled trips.
- Opt into optional AI extraction when a backend OpenAI key is configured; failures preserve the original story with an explicitly labeled fallback.
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

Copy `work/.env.example` to `work/.env`, fill `OPENAI_API_KEY` locally and optionally set `OPENAI_MODEL`. The combined start command loads this file. For separate terminals, export these variables in the Python terminal. Restart the backend after changes.

The contribution form then offers an explicit opt-in checkbox. Only submitted story text and the public place catalog are sent to OpenAI. Keys never reach the frontend. The adapter uses the [Responses API structured-output format](https://developers.openai.com/api/docs/guides/structured-outputs), validates returned IDs against the catalog, does not request API response storage, and retains a local fallback. A live paid API request has not been exercised in this build.

## Data and scope

`work/backend/roam.db` is created on first start and excluded from Git. Guest ownership is based on an HttpOnly, SameSite cookie; clearing that cookie loses access to that session’s data. This is a local pilot, not production authentication. Keep the server bound to loopback.

The venue hours, costs, review counts, SLH ratings and contributor identities are **sample data**, not live or verified information. Some meal stops represent suggested experiences rather than verified businesses. Routes are approximate walking estimates with schematic connecting lines, not road routing. Food and local transport have a separate ₹400 daily allowance. Stay and travel to Kochi are excluded.

SLH = `(Safety + Legitimacy + Hygiene) / 15 × 100`, with each dimension rated 1–5. Missing or invalid dimensions result in no rating. An itinerary’s score averages its stop dimensions equally. No score certifies safety. No actual reviews are collected yet.

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
