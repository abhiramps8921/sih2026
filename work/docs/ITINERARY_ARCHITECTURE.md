# Validated itinerary planning

## Presentation explanation

**Python owns facts and guarantees; AI owns judgement and planning.**

Previously: structured preferences -> AI place names -> local catalog matching -> AI ranking -> Python selected, ordered and timed every stop. Replacement regenerated the entire trip. The route badge always claimed geographic clustering.

Now:

1. Keep the current structured inputs and optionally add a written trip description.
2. AI discovers a broad set of catalog candidates (requested range: 25-60).
3. Python resolves names to local catalog records, deduplicates accent/case variants, applies budget/area/SLH/exclusion filters, checks coordinates, and rejects geographic outliers. Unknown AI venues are discarded; catalog costs, hours and coordinates remain authoritative for this demo.
4. Python supplies a shortlist with alternatives (normally at least 15 when available, scaled for more days and capped at 60), Haversine distances, and estimated travel minutes.
5. AI selects stops, orders them, assigns times and purposes, considers meals and sunset, and interprets the full written request. It must return JSON with allowed place IDs.
6. Python validates structure, days, IDs, duplicates, geography, hours, duration, travel gaps, meal timing, usable stop count and daily cost including the existing INR 400 allowance.
7. An invalid response receives exactly one repair attempt with the same preferences, shortlist, geographic context, attempted result and structured validation errors.
8. API failure, timeout, or a still-invalid repair uses the deterministic local planner. Its output is also validated. Insufficient feasible places produce the existing actionable error instead of an invalid saved trip.
9. Build the ordered day stops, costs, numbering and clustering metadata. Save in the existing SQLite JSON column. Cards and map consume the same day stop array and number.

## Editing

Replace stop tries eligible nearby alternatives, checks interests through the existing local score, keeps the other stop identities and other days, repairs the affected day's timing, and validates the entire result. Failed candidates never overwrite the saved trip. Removal preserves intentional visit times, recalculates travel and cost, validates, and renumbers the remaining stops.

A route is labelled **Area-clustered** only when it has at least two stops and every pair is within 6 km. Geography uses a conservative 22 km city radius around the configured Kochi centre, a 65 km maximum excursion radius, a 20 km consecutive-leg limit and a 25 km daily diameter. These are demo policy thresholds, not administrative boundaries. Excursions require `allow_day_trips` or a direct request such as “include a day trip”; negative requests take precedence. Excursions still need a coherent route within the daily limits.

## Responsibility split

| Python | AI |
| --- | --- |
| Local facts, identity, exclusions, geography and distances | Understand nuanced trip preferences |
| Budget arithmetic, valid time windows and travel gaps | Choose among eligible candidates |
| Structured validation and one-repair orchestration | Sequence visits, meals and breaks |
| Deterministic fallback and safe local replacement | Decide pacing, grouping and overall experience |
| Canonical ordering, numbering and SQLite persistence | Repair its attempted schedule from explicit errors |

## Changed files

- `backend/ai.py`: candidate metadata and strict itinerary JSON contract; planning and repair prompt replace ranking.
- `backend/planner.py`: discovery/shortlist/planning/repair/fallback pipeline and local replacement.
- `backend/planning_rules.py`: shared facts, filtering, geography, meal windows, validator and canonical output helpers.
- `backend/app.py`: optional written request, explicit exclusions/day-trip preference, validated edit endpoints.
- `src/Trips.jsx`: optional text field, canonical card numbering, conditional cluster label.
- `src/TripMap.jsx`: canonical marker and popup numbering.
- `backend/test_api.py`: existing AI pipeline test now checks actual planning.
- `backend/test_planning.py`: focused validation, repair, fallback, prompt, editing and persistence regressions.
- `docs/ITINERARY_ARCHITECTURE.md`: this explanation and verification notes.
- `../README.md`: link and updated AI behaviour.

No dependencies, SQLite migration, visual redesign or deployment changes are required. Place records continue to come from the existing Python/JSON catalog; SQLite continues to store accounts, trips, drafts and progress.

## Verification

From `work/`:

```powershell
.\.venv\Scripts\python -m pytest backend -q
.\.venv\Scripts\python -m ruff check backend
.\.venv\Scripts\python -m ruff format --check backend
npm test
npm run build
npm run format:check
```

Coverage includes accent duplicates, invalid coordinates, distant venues, geographic jumps, unknown IDs, duplicate visits across days, broken JSON, overlaps, duration, meal windows, total budget, unchanged repair context, exactly one repair, provider failure, multiday fallback, replacement preserving other days, and persisted request/numbering after removal. Provider responses are mocked in automated tests. Frontend tests include marker-label ordering and separation.

## Remaining limits

- This remains a Kochi catalog demo. It cannot safely add previously unknown destinations from AI discovery.
- Catalog prices, opening hours and ratings are sample estimates, not verified real-time facts. Straight-line distances and estimated transit times do not account for road topology, ferry schedules or traffic.
- AI must be available to interpret arbitrary natural-language preferences. Offline fallback honours structured constraints and a small set of direct exclusions, but does not fully interpret nuances such as walking tolerance or guarantee a sunset visit.
- “Enough stops” permits a reduced count when constraints are tight. A validated AI plan normally needs at least two stops per day when candidates and the requested count permit; fallback may return one usable stop with a warning. Impossible constraints still produce a clear error.
- Local replacement optimizes proximity and structured interests; it does not call AI again to reinterpret nuanced preferences.
- Live Gemini compatibility and subjective trip quality have not been verified in this change: automatic approval review requires explicit user permission to send demo preferences and catalog data to Google. That permission is pending. The configured key was not exposed or changed.
- No browser visual walkthrough was performed. The UI change is limited to one optional field and existing labels/numbering; the production build and frontend checks passed.
