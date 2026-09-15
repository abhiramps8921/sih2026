import logging
import math
import re
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher

from . import ai
from .catalog import BY_ID, PLACES, TEMPLATE_STOPS, slh_score

logger = logging.getLogger(__name__)


def travel_estimate(a, b):
    """Return a conservative city travel estimate, not live routing."""
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = lat2 - lat1
    dlng = math.radians(b["lng"] - a["lng"])
    distance = (
        6371
        * 2
        * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin(dlat / 2) ** 2
                    + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
                ),
            )
        )
    )
    road_distance = distance * 1.3
    if road_distance <= 2:
        return max(10, math.ceil(road_distance / 4 * 60)), "walk"
    return max(15, math.ceil(road_distance / 22 * 60) + 8), "local transit"


def travel_minutes(a, b):
    return travel_estimate(a, b)[0]


def time_label(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _normalise_name(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def venue_key(place):
    catalog_place = BY_ID.get(place.get("id"), {})
    area = place.get("area") or catalog_place.get("area")
    name = place.get("name") or catalog_place.get("name")
    if not area or not name:
        raise ValueError("A venue needs an area and name for itinerary deduplication")
    return area, _normalise_name(name)


def _match_candidate_names(candidates, available):
    """Resolve AI names to catalog records without accepting unknown places."""
    matches = []
    for candidate in candidates:
        target = _normalise_name(candidate.name)
        exact = [place for place in available if _normalise_name(place["name"]) == target]
        if exact:
            # Prefer the record carrying richer local metadata when names are duplicated.
            matches.append(max(exact, key=lambda place: ("local_rating" in place, "worth_it_score" in place)))
            continue
        best = max(
            available,
            key=lambda place: SequenceMatcher(None, target, _normalise_name(place["name"])).ratio(),
            default=None,
        )
        if best and SequenceMatcher(None, target, _normalise_name(best["name"])).ratio() >= 0.78:
            matches.append(best)
    return list({place["id"]: place for place in matches}.values())


def fallback_score(place, preferences, *, requested=False):
    """Normalized deterministic local score; absent catalog facts contribute zero."""
    tags = {str(tag).lower() for tag in place.get("tags", [])}
    category = place["category"].lower()
    interests = {interest.lower() for interest in preferences.interests}
    interest_match = 30 if category in interests or tags & interests else 0
    local_rating = min(max(float(place.get("local_rating", 0)), 0), 5) * 2
    worth_it = min(max(float(place.get("worth_it_score", 0)), 0), 10) * 2
    daily_budget = preferences.budget - 400
    budget_match = 15 if place["cost"] <= daily_budget else -30
    slh = (slh_score(place["slh"]) or 0) / 10
    travel_type_match = 8 if preferences.travel_type and preferences.travel_type in place.get("recommended_for", []) else 0
    requested_bonus = 40 if requested else 0
    return interest_match + local_rating + worth_it + budget_match + slh + travel_type_match + requested_bonus


def _eligible_places(preferences, excluded):
    return [
        place
        for place in PLACES
        if place["id"] not in excluded
        and place["cost"] + 400 <= preferences.budget
        and (not preferences.areas or place["area"] in preferences.areas)
        and (not preferences.min_slh or (slh_score(place["slh"]) or 0) >= preferences.min_slh)
    ]


def _rank_places(preferences, available, chosen_ids, *, allow_ai=True):
    """Use Gemini only as a ranking signal; local score remains the safe baseline."""
    local_ranked = sorted(
        available,
        key=lambda place: (fallback_score(place, preferences, requested=place["id"] in chosen_ids), place["id"]),
        reverse=True,
    )
    if not allow_ai:
        return local_ranked, "fallback"
    try:
        ai_candidates = _match_candidate_names(ai.generate_candidates(preferences), available)
        if not ai_candidates:
            raise ai.GeminiUnavailableError("Gemini candidates did not match the local catalog")
        ai_ids = ai.rerank_places(preferences, ai_candidates)
        ai_order = {place_id: len(ai_ids) - index for index, place_id in enumerate(ai_ids)}
        # Keep local candidates Gemini omitted so itinerary feasibility is never compromised.
        ranked = sorted(
            available,
            key=lambda place: (
                fallback_score(place, preferences, requested=place["id"] in chosen_ids)
                + ai_order.get(place["id"], 0) * 4,
                place["id"],
            ),
            reverse=True,
        )
        return ranked, "ai"
    except ai.GeminiUnavailableError:
        return local_ranked, "fallback"
    except Exception:
        logger.exception("Gemini recommendation failed unexpectedly. Falling back to local recommendation engine.")
        return local_ranked, "fallback"


def generate_plan(preferences, *, excluded=None, requested=None, allow_ai=True):
    budget = preferences.budget
    chosen_ids = requested or TEMPLATE_STOPS.get(preferences.template_id, [])
    excluded = set(excluded or [])
    excluded_venues = {venue_key(BY_ID[id]) for id in excluded if id in BY_ID}
    excluded.update(p["id"] for p in PLACES if venue_key(p) in excluded_venues)
    available = _eligible_places(preferences, excluded)
    # Catalog imports can describe a curated venue under a different ID.
    venues = {}
    for place in available:
        key = venue_key(place)
        if key not in venues or (
            place["id"] in chosen_ids and venues[key]["id"] not in chosen_ids
        ):
            venues[key] = place
    available = list(venues.values())
    candidates, recommendation_mode = _rank_places(
        preferences, available, chosen_ids, allow_ai=allow_ai
    )
    used, days, warnings = set(), [], []
    target = preferences.stops_per_day
    if target is None:
        target = {"relaxed": 3, "balanced": 4, "packed": 5}[preferences.pace]
    for day in range(preferences.days):
        clock, spent, stops = 9 * 60, 0, []
        previous = None
        remaining = [p for p in candidates if p["id"] not in used]
        days_left = preferences.days - day
        day_target = min(target, max(1, math.ceil(len(remaining) / days_left)))
        for _ in range(day_target):
            feasible = []
            slots_left = day_target - len(stops)
            ideal_cost = max(0, (budget - 400 - spent) / slots_left)
            for p in remaining:
                travel, travel_mode = travel_estimate(previous, p) if previous else (0, "start")
                start = max(clock + travel, p["opens"] * 60)
                # Reserve food + local transport per day, outside each stop's cost.
                if spent + p["cost"] + 400 > budget or start + p["duration"] > min(
                    22 * 60, p["closes"] * 60
                ):
                    continue
                preference = (80 if p["id"] in chosen_ids else 0) + (
                    40 if p["category"] in preferences.interests else 0
                )
                cost_gap = abs(p["cost"] - ideal_cost) / max(ideal_cost, 1)
                budget_fit = 45 - min(cost_gap, 1.5) * 45
                premium_bonus = 45 if budget >= 5000 and p["price_tier"] == "premium" else 0
                rank = (
                    preference
                    + budget_fit
                    + premium_bonus
                    + (slh_score(p["slh"]) or 0) / 10
                    + (18 if previous and previous["area"] == p["area"] else 0)
                    + fallback_score(p, preferences, requested=p["id"] in chosen_ids) / 4
                    - sum(stop["place"]["category"] == p["category"] for stop in stops) * 12
                    - travel / 5
                    - max(0, start - clock - travel) / 5
                )
                feasible.append((rank, p, travel, travel_mode, start))
            if not feasible:
                break
            _, picked, travel, travel_mode, start = max(feasible, key=lambda item: item[0])
            stops.append(
                dict(
                    id=f"d{day + 1}-{picked['id']}",
                    place=picked,
                    start=time_label(start),
                    end=time_label(start + picked["duration"]),
                    travel_minutes=travel,
                    travel_mode=travel_mode,
                    completed=False,
                )
            )
            used.add(picked["id"])
            remaining = [p for p in remaining if p["id"] != picked["id"]]
            spent += picked["cost"]
            clock = start + picked["duration"] + 20
            previous = picked
        if not stops:
            raise ValueError(
                "No feasible stops fit this plan. Increase your budget or lower the SLH filter."
            )
        if len(stops) < day_target:
            warnings.append(
                f"Day {day + 1} has fewer stops to respect your budget and available time."
            )
        day_cost = spent + 400
        utilization = round(day_cost / budget * 100)
        if budget >= 5000 and utilization < 60:
            warnings.append(
                f"Day {day + 1} uses {utilization}% of the budget because matching available "
                "experiences did not fit the opening hours and travel time."
            )
        days.append(
            dict(
                day=day + 1,
                date=str(preferences.start_date + timedelta(days=day)),
                stops=stops,
                cost=day_cost,
                budget_utilization=utilization,
            )
        )
    used_venues = {venue_key(BY_ID[id]) for id in used}
    missed = [
        BY_ID[id]["name"] for id in chosen_ids if venue_key(BY_ID[id]) not in used_venues
    ]
    if missed:
        warnings.append(
            "Some requested stops did not fit the constraints: " + ", ".join(missed) + "."
        )
    return dict(
        title=preferences.title or "Your little Kochi escape",
        city="Kochi",
        days=days,
        preferences=preferences.model_dump(mode="json"),
        total_cost=sum(d["cost"] for d in days),
        budget_utilization=round(sum(d["cost"] for d in days) / (budget * preferences.days) * 100),
        warnings=warnings,
        method=("Gemini-assisted local planner" if recommendation_mode == "ai" else "Rule-based local planner"),
        recommendation_mode=recommendation_mode,
        routing="Estimated walking or local-transit time; map lines are not road directions",
        cost_note="Per person. The planner aims to use the available daily budget without exceeding it and includes ₹400/day for food and local transport. Stay and travel to Kochi are excluded. Venue prices and hours are sample estimates.",
    )
