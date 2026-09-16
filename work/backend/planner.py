import logging
import math
from datetime import timedelta

from . import ai
from .catalog import BY_ID, PLACES, TEMPLATE_STOPS, slh_score
from .planning_rules import (
    MAX_DAY_DIAMETER_KM,
    MAX_LEG_KM,
    _normalise_name,
    canonical_days,
    distance_km,
    filter_places,
    geographic_context,
    meal_start,
    raw_itinerary,
    refresh_totals,
    time_label,
    travel_estimate,
    validate_itinerary,
    venue_key,
)

logger = logging.getLogger(__name__)


def _match_candidate_names(candidates, available):
    """Resolve AI names to catalog records without accepting unknown places."""
    matches = []
    for candidate in candidates:
        target = _normalise_name(candidate.name)
        exact = [place for place in available if _normalise_name(place["name"]) == target]
        if exact:
            # Prefer the record carrying richer local metadata when names are duplicated.
            matches.append(
                max(exact, key=lambda place: ("local_rating" in place, "worth_it_score" in place))
            )
            continue
        logger.info("[FILTER] Removed %s: no exact local catalog match", candidate.name)
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
    travel_type_match = (
        8
        if preferences.travel_type and preferences.travel_type in place.get("recommended_for", [])
        else 0
    )
    requested_bonus = 40 if requested else 0
    return (
        interest_match
        + local_rating
        + worth_it
        + budget_match
        + slh
        + travel_type_match
        + requested_bonus
    )


def _eligible_places(preferences, excluded, catalog=None):
    return [
        place
        for place in (PLACES if catalog is None else catalog)
        if place["id"] not in excluded
        and place["cost"] + 400 <= preferences.budget
        and (not preferences.areas or place["area"] in preferences.areas)
        and (not preferences.min_slh or (slh_score(place["slh"]) or 0) >= preferences.min_slh)
    ]


def _fallback_plan(preferences, candidates, chosen_ids):
    budget = preferences.budget
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
                start = meal_start(p, max(clock + travel, p["opens"] * 60))
                if previous and distance_km(previous, p) > MAX_LEG_KM:
                    continue
                if stops and any(distance_km(s["place"], p) > MAX_DAY_DIAMETER_KM for s in stops):
                    continue
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
                    - travel * 2
                    - max(0, start - clock - travel) / 5
                )
                if preferences.stops_per_day is not None:
                    # Explicit counts need time reserved for the remaining visits and breaks.
                    time_per_slot = max(1, (22 * 60 - clock) / slots_left)
                    required_time = start - clock + p["duration"] + 20
                    rank -= 120 * required_time / time_per_slot
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
        if len(stops) < target:
            warnings.append(
                f"Day {day + 1}: scheduled {len(stops)} of {target} requested stops. "
                "The remaining stops could not fit the available places, opening hours, "
                "visit durations, travel, 20-minute breaks and daily budget. "
                "Try fewer stops per day, more areas or a higher budget."
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
    missed = [BY_ID[id]["name"] for id in chosen_ids if venue_key(BY_ID[id]) not in used_venues]
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
        method="Rule-based local planner",
        recommendation_mode="fallback",
        routing="Estimated walking or local-transit time; map lines are not road directions",
        cost_note="Per person. The planner aims to use the available daily budget without exceeding it and includes ₹400/day for food and local transport. Stay and travel to Kochi are excluded. Venue prices and hours are sample estimates.",
    )


def generate_plan(preferences, *, excluded=None, requested=None, allow_ai=True, catalog=None):
    chosen_ids = requested or TEMPLATE_STOPS.get(preferences.template_id, [])
    excluded = set(excluded or []) | set(preferences.excluded_place_ids)
    available = filter_places(
        _eligible_places(preferences, excluded, catalog), preferences, excluded
    )
    local = sorted(
        available,
        key=lambda p: (fallback_score(p, preferences, requested=p["id"] in chosen_ids), p["id"]),
        reverse=True,
    )
    discovered = []
    if allow_ai:
        try:
            suggestions = ai.generate_candidates(preferences)
            logger.info("[PLANNER] Generated %s candidates", len(suggestions))
            discovered = _match_candidate_names(suggestions, available)
        except Exception:
            logger.warning("[PLANNER] Candidate discovery unavailable; using local catalog")
    # Leave room for alternatives; keep the full catalog for offline feasibility.
    target = (
        preferences.stops_per_day or {"relaxed": 3, "balanced": 4, "packed": 5}[preferences.pace]
    )
    shortlist = list(
        {
            p["id"]: p for p in [p for p in local if p["id"] in chosen_ids] + discovered + local
        }.values()
    )[: min(60, max(15, target * preferences.days * 3))]
    if allow_ai:
        context = geographic_context(shortlist)
        context["requested_place_ids"] = chosen_ids
        attempted, errors = None, None
        for attempt in range(2):
            try:
                logger.info(
                    "[%s] Sent %s candidates",
                    "AI-REPAIR" if attempt else "AI-PLANNER",
                    len(shortlist),
                )
                attempted = ai.plan_itinerary(
                    preferences, shortlist, context, attempted=attempted, errors=errors
                )
                parsed, errors = validate_itinerary(attempted, shortlist, preferences)
                if not errors:
                    plan = {
                        "title": preferences.title or "Your little Kochi escape",
                        "city": "Kochi",
                        "preferences": preferences.model_dump(mode="json"),
                        "days": canonical_days(parsed, shortlist, preferences),
                        "routing": "Estimated walking or local-transit time; map lines are not road directions",
                        "cost_note": "Per person; includes 400 INR/day for food and local transport. Venue prices and hours are sample estimates. Stay and travel to Kochi excluded.",
                    }
                    plan["method"] = "Validated AI itinerary planner"
                    plan["recommendation_mode"] = "ai"
                    plan["warnings"] = [
                        f"Day {d.day}: scheduled {len(d.stops)} of {target} requested stops within the constraints."
                        for d in parsed.days
                        if len(d.stops) < target
                    ]
                    plan["planning_source"] = "ai_repair" if attempt else "ai"
                    logger.info("[PLANNER] AI %s successful", "repair" if attempt else "planning")
                    return refresh_totals(plan)
            except ai.GeminiUnavailableError:
                logger.warning("[FALLBACK] AI unavailable; using deterministic planner")
                break
            except Exception:
                logger.exception("[FALLBACK] Unexpected AI failure; using deterministic planner")
                break
    fallback = _fallback_plan(preferences, local, chosen_ids)
    parsed, errors = validate_itinerary(raw_itinerary(fallback), local, preferences)
    # A constrained fallback can legitimately have fewer stops, with an existing user warning.
    serious = [error for error in errors if error["type"] != "TOO_FEW_STOPS"]
    if serious:
        raise ValueError(
            "No valid itinerary fits these constraints. Try more areas or a higher budget."
        )
    fallback["planning_source"] = "fallback"
    logger.info("[FALLBACK] Validated deterministic itinerary")
    return refresh_totals(fallback)


def replace_stop(plan, selected, preferences, excluded, *, catalog=None):
    """Try nearby alternatives in place, preserving all other stops and days."""
    from copy import deepcopy

    occupied = {s["place"]["id"] for d in plan["days"] for s in d["stops"]}
    candidates = filter_places(
        _eligible_places(preferences, excluded | occupied, catalog),
        preferences,
        excluded | occupied,
    )
    candidates.sort(
        key=lambda p: (
            distance_km(selected["place"], p) - fallback_score(p, preferences) / 100,
            p["id"],
        )
    )
    for candidate in candidates:
        revised = deepcopy(plan)
        for day in revised["days"]:
            if not any(s["id"] == selected["id"] for s in day["stops"]):
                continue
            previous, clock = None, 540
            for stop in day["stops"]:
                if stop["id"] == selected["id"]:
                    stop.update(
                        id=f"d{day['day']}-{candidate['id']}", place=candidate, purpose="visit"
                    )
                p = stop["place"]
                travel, mode = travel_estimate(previous, p) if previous else (0, "start")
                # Preserve intentional meal/sunset times when shifting later stops.
                from .planning_rules import minutes

                start = meal_start(p, max(clock + travel, p["opens"] * 60, minutes(stop["start"])))
                stop.update(
                    start=time_label(start),
                    end=time_label(start + p["duration"]),
                    travel_minutes=travel,
                    travel_mode=mode,
                )
                previous, clock = p, start + p["duration"] + 20
        allowed = [s["place"] for d in revised["days"] for s in d["stops"]]
        _, errors = validate_itinerary(raw_itinerary(revised), allowed, preferences)
        if not errors:
            revised["excluded_places"] = sorted(excluded)
            revised["method"] = "Validated local route repair"
            revised["planning_source"] = "local_repair"
            revised["recommendation_mode"] = "fallback"
            revised["warnings"] = []
            return refresh_totals(revised)
    raise ValueError(
        "No replacement fits this day's route, hours and budget. Your original plan is unchanged."
    )
