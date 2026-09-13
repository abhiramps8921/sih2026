import math
from datetime import timedelta

from .catalog import BY_ID, PLACES, TEMPLATE_STOPS, slh_score


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


def generate_plan(preferences, *, excluded=None, requested=None):
    budget = preferences.budget
    chosen_ids = requested or TEMPLATE_STOPS.get(preferences.template_id, [])
    excluded = set(excluded or [])
    candidates = [
        p
        for p in PLACES
        if p["id"] not in excluded
        and (not preferences.areas or p["area"] in preferences.areas)
        and (not preferences.min_slh or (slh_score(p["slh"]) or 0) >= preferences.min_slh)
    ]
    candidates.sort(
        key=lambda p: (
            p["id"] in chosen_ids,
            p["category"] in preferences.interests,
            slh_score(p["slh"]),
        ),
        reverse=True,
    )
    used, days, warnings = set(), [], []
    target = {"relaxed": 3, "balanced": 4, "packed": 5}[preferences.pace]
    for day in range(preferences.days):
        clock, spent, stops = 9 * 60, 0, []
        previous = None
        remaining = [p for p in candidates if p["id"] not in used]
        days_left = preferences.days - day
        day_target = min(target, max(1, math.ceil(len(remaining) / days_left)))
        for _ in range(day_target):
            feasible = []
            for p in remaining:
                travel, travel_mode = travel_estimate(previous, p) if previous else (0, "start")
                start = max(clock + travel, p["opens"] * 60)
                # Reserve food + local transport per day, outside each stop's cost.
                if spent + p["cost"] + 400 > budget or start + p["duration"] > min(
                    18 * 60, p["closes"] * 60
                ):
                    continue
                preference = (80 if p["id"] in chosen_ids else 0) + (
                    40 if p["category"] in preferences.interests else 0
                )
                rank = (
                    preference
                    + (slh_score(p["slh"]) or 0) / 10
                    + (18 if previous and previous["area"] == p["area"] else 0)
                    - travel / 5
                    - max(0, start - clock - travel) / 10
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
        days.append(
            dict(
                day=day + 1,
                date=str(preferences.start_date + timedelta(days=day)),
                stops=stops,
                cost=spent + 400,
            )
        )
    missed = [BY_ID[id]["name"] for id in chosen_ids if id not in used]
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
        warnings=warnings,
        method="Rule-based local planner",
        routing="Estimated walking or local-transit time; map lines are not road directions",
        cost_note="Per person. Includes ₹400/day food and local transport allowance; excludes stay and travel to Kochi. Venue prices and hours are sample estimates.",
    )
