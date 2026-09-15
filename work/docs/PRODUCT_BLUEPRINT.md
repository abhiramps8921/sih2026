# Roam product blueprint

## Product idea

Roam is a community travel application where people who know a destination share places and real trip experiences. Travelers can browse those contributions or generate a practical day-by-day itinerary based on trip length, daily budget, interests and pace.

The core loop is:

1. A local or traveler shares places or raw trip notes.
2. The app structures the story into an editable itinerary draft.
3. Another traveler personalizes and saves the itinerary.
4. The traveler follows the timeline, map and local tips.
5. Completed stops earn points and badges.

## Pilot scope

The MVP focuses on Kochi, Kerala, with seeded sample content. It includes:

- 18 sample places spanning food, culture, nature, art and hidden gems.
- 4 browsable itinerary collections.
- Search and interest filters.
- 1–3 day itinerary generation.
- Daily budget, interests, pace, date and minimum SLH preferences.
- Time-window-aware scheduling, approximate walking time and breaks.
- Day timelines, map pins and external walking directions.
- Saved trips, stop replacement/removal, completion, points and badges.
- Private contribution drafts and story-to-trip conversion.
- Optional AI-assisted story extraction with an explicit opt-in.
- A labeled demonstration of group discovery and join requests.

Authentication, public publishing, payments, real-time chat, live stranger matching, review moderation, multi-city scale and native application packaging remain future work.

## SLH score

SLH means Safety, Legitimacy and Hygiene. Each dimension is rated from 1 to 5. A place score is calculated as:

`(Safety + Legitimacy + Hygiene) / 15 × 100`

Legitimacy is the inverse of scam risk. A higher L rating means stronger confidence that the listing, operator, prices and promised experience are authentic and transparent.

An itinerary score averages each dimension across its included places before applying the same formula. A missing or invalid dimension makes the item unrated. The interface shows the dimensions, sample size, evidence date and source status rather than presenting only a composite number.

The seeded values are illustrative demo data. SLH is not a certification or safety guarantee. A production design should separate verified evidence, recent reviews, unresolved reports and low-volume uncertainty.

## Itinerary engine

The deterministic planner owns feasibility. It:

1. Validates days, budget, pace, interests and minimum SLH.
2. Filters the place catalog.
3. Ranks requested and relevant places, including cost fit against the remaining daily budget.
4. Accounts for travel time and opening windows.
5. Fits 3 stops, 5 stops or a custom target of up to 20 stops per day.
6. Adds a 20-minute buffer between visits.
7. Reserves ₹400 per day for food and local transport outside listed stop costs.
8. Favors premium dining and activities when a larger budget makes them appropriate.
9. Returns warnings when requested stops do not fit or the available catalog cannot use a healthy share of the budget.

Travel times are geographic estimates, and map lines are schematic. A production release should replace them with a real routing provider.

AI is limited to extracting mentioned catalog places, a short summary and unresolved names from raw travel notes. It cannot create coordinates, prices, hours or safety claims. Output uses a strict schema and still requires contributor review. If AI fails or is not configured, the app preserves the original notes and uses catalog matching.

## Trust and social design

- Contributor identities and reviews in the pilot are labeled as samples.
- Guest-owned records are isolated using an HttpOnly, SameSite cookie.
- Story drafts remain private and preserve their original notes.
- Social discovery requires explicit action and is demo-only.
- No live person is contacted by a group request.
- Production matching requires authenticated profiles, blocking, reporting, moderation, capacity enforcement and private group chat.
- Meetups should use public, popular locations and never expose accommodation addresses.

## Architecture

- React and JavaScript frontend with responsive desktop/mobile layouts.
- FastAPI backend with validated request models.
- SQLite for local durable state.
- Leaflet and OpenStreetMap for map display.
- Optional Google Gemini Interactions API integration on the backend.
- GitHub Actions for frontend build, formatting and backend/frontend tests.

The frontend never receives service credentials. All persistent mutations pass through backend ownership checks. Completion records use a unique trip-and-stop key so retries cannot award points twice.

## Presentation flow

1. Open Explore and show the Kochi collection.
2. Open an SLH breakdown and explain the three dimensions.
3. Build a 2-day trip from budget and interest preferences.
4. Show the generated timeline and map.
5. Replace or remove a stop and show the updated schedule.
6. Complete a stop and show points on the profile.
7. Save raw trip notes, review recognized places and create a schedule.
8. Show the community screen while clearly stating that matching is a demo.

The pitch is: reliable local context, practical scheduling and transparent trust signals in one followable trip.
