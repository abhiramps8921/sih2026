# Roam build decisions

## Scope
Local responsive JavaScript web app + Python API. Pilot: Kochi. Core loop: browse, generate, save, follow, complete. Travel stories are reviewed drafts; place ratings and local tips are unverified account contributions. Community groups support direct joining. No claims of verified safety.

## Stack
React + Vite for a responsive web-first application, FastAPI + SQLite for local durable state. SQLite keeps the local demo self-contained; database access stays on the server. No browser-only substitute for saved trips. HttpOnly session cookies resolve account or isolated guest ownership. Place contributions require an account and a selected role.

## SLH
Safety, Legitimacy, Hygiene are separate 1–5 community-review dimensions. Legitimacy measures scam resistance: a higher L score means a traveler is less likely to encounter misleading listings, hidden charges, impersonation, bait-and-switch tactics or an untrustworthy operator. Display the composite on a 100-point scale: (S + L + H) / 15 * 100. Require all dimensions. Missing data means unrated. Show sample count, source status, and review date. Seeded ratings are always labeled demo; no score is a guarantee. Do not fabricate live reviews.

## Milestones
1. Foundation and design skills.
2. Responsive discovery and trip detail surfaces.
3. Durable API: scheduling, trips, completion, rewards, contribution drafts, demo groups.
4. Browser and API verification; accessibility/responsive fixes.

## Boundaries
Costs/hours are sample estimates. Routing uses coordinate-based estimates and schematic lines, not road navigation. AI provider integration is optional; rule-based structuring is labeled honestly when no key is configured. No hosted release or public social access in this local build.

## Place ratings and local tips

Use **Add rating / tip** in the header, **Rate** on mobile, or a place's SLH dialog / active-trip action. `/rate?place=<catalog-id>` preselects a location. A signed-in, role-selected account can submit all three SLH dimensions, a tip of up to 500 characters, or both, with a non-future visit date and a personal-experience acknowledgement. Returning to a place edits the same contribution; deletion removes it. Completed visits are self-reported, never verified.

SQLite `place_contributions` has a unique account/place key and separate rating/tip moderation statuses. `/api/places/{id}/contribution` supports GET, PUT and DELETE; `/api/places/{id}/tips` lists paginated public tips; `/api/tips/{id}/reports` accepts one report per account. Public tips never expose contributor email or account IDs. React renders tip text as escaped text. Input validation rejects excessive links and repeated-character spam.

Community averages never include illustrative seed votes. One or two distinct account ratings display immediately as an **Early community signal**. At three ratings, community SLH replaces demo SLH in filters and planning. Below that threshold, demo values remain labeled DEMO, and locations without demo values remain unrated. Catalog responses, saved-trip hydration, new plans and replacements use current aggregates. Itinerary summaries label mixed sources.

A first report excludes a tip from public responses as reported; three distinct reports mark it hidden pending review. Edits preserve reports and moderation state. Ratings have independent moderation status and are unaffected by tip reports. Authors can delete contributions; a production system still needs an administrator review queue and stronger abuse controls, including protection against delete-and-repost and multiple-account abuse. All observations are unverified and no score guarantees safety.
