# Roam build decisions

## Scope
Local responsive JavaScript web app + Python API. Pilot: Kochi. Core loop: browse, generate, save, follow, complete. Contributions are reviewed drafts. Social departures are explicitly demo-only. No public stranger matching or claims of verified safety.

## Stack
React + Vite for a responsive web-first application, FastAPI + SQLite for local durable state. SQLite keeps the local demo self-contained; database access stays on the server. No browser-only substitute for saved trips. Session cookie identifies guest ownership. No production authentication.

## SLH
Safety, Legitimacy, Hygiene are separate 1–5 community-review dimensions. Legitimacy measures scam resistance: a higher L score means a traveler is less likely to encounter misleading listings, hidden charges, impersonation, bait-and-switch tactics or an untrustworthy operator. Display the composite on a 100-point scale: (S + L + H) / 15 * 100. Require all dimensions. Missing data means unrated. Show sample count, source status, and review date. Seeded ratings are always labeled demo; no score is a guarantee. Do not fabricate live reviews.

## Milestones
1. Foundation and design skills.
2. Responsive discovery and trip detail surfaces.
3. Durable API: scheduling, trips, completion, rewards, contribution drafts, demo groups.
4. Browser and API verification; accessibility/responsive fixes.

## Boundaries
Costs/hours are sample estimates. Routing uses coordinate-based estimates and schematic lines, not road navigation. AI provider integration is optional; rule-based structuring is labeled honestly when no key is configured. No hosted release or public social access in this local build.
