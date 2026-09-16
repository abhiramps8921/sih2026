"""Deterministic itinerary facts and validation shared by AI, fallback and edits."""

import logging
import math
import re
import unicodedata

from . import ai
from .catalog import BY_ID

logger = logging.getLogger(__name__)


def travel_estimate(a, b):
    """Return a conservative city travel estimate, not live routing."""
    road_distance = distance_km(a, b) * 1.3
    if road_distance <= 2:
        return max(10, math.ceil(road_distance / 4 * 60)), "walk"
    return max(15, math.ceil(road_distance / 22 * 60) + 8), "local transit"


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


# City scope is intentionally conservative for this Kochi-only demo.
CITY_CENTER = {"lat": 9.9816, "lng": 76.2999}
CITY_RADIUS_KM = 22
EXCURSION_RADIUS_KM = 65
MAX_LEG_KM = 20
MAX_DAY_DIAMETER_KM = 25
CLUSTER_DIAMETER_KM = 6


def distance_km(a, b):
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    value = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(b["lng"] - a["lng"]) / 2) ** 2
    )
    return 12742 * math.asin(min(1, math.sqrt(value)))


def explicitly_excluded(place, request):
    """Recognize direct named exclusions only; nuanced preferences remain AI's job."""
    text = unicodedata.normalize("NFKD", request).encode("ascii", "ignore").decode().lower()
    names = [place["name"], place.get("area_name", "")]
    for name in names:
        normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
        if normalized and re.search(
            r"(?:avoid|skip|exclude|already visited|don't want to visit)\s+"
            + re.escape(normalized)
            + r"(?![a-z])",
            text,
        ):
            return True
    metadata = " ".join(str(place.get(key, "")) for key in ("name", "category", "tags")).lower()
    if (
        re.search(r"\b(?:no|avoid|skip|exclude|don't want)\s+museums?\b", text)
        and "museum" in metadata
    ):
        return True
    return False


def allows_day_trips(preferences):
    text = preferences.custom_request.lower()
    if re.search(
        r"\b(?:no|avoid|skip|exclude|don't want|do not want|don't include|do not include)\s+(?:any )?day[- ]trips?\b",
        text,
    ):
        return False
    return preferences.allow_day_trips or bool(
        re.search(
            r"\b(?:include|want|allow|open to|plan)(?: a| nearby)? day[- ]trips?\b",
            text,
        )
    )


def filter_places(places, preferences, excluded=()):
    """Use local facts and reject invalid venues before either planner sees them."""
    excluded_names = {_normalise_name(BY_ID[id]["name"]) for id in excluded if id in BY_ID}
    seen, valid = set(), []
    for source in places:
        place = dict(source)
        name = _normalise_name(place.get("name", ""))
        reason = None
        values = [place.get(key) for key in ("lat", "lng", "cost", "duration", "opens", "closes")]
        if not name or any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
            for v in values
        ):
            reason = "invalid data"
        elif not (-90 <= place["lat"] <= 90 and -180 <= place["lng"] <= 180):
            reason = "invalid coordinates"
        elif not (
            0 <= place["cost"] <= preferences.budget - 400
            and 0 < place["duration"] <= 780
            and 0 <= place["opens"] < place["closes"] <= 24
        ):
            reason = "invalid costs, duration or hours"
        elif preferences.areas and place.get("area") not in preferences.areas:
            reason = "outside requested areas"
        elif name in seen:
            reason = "duplicate"
        elif (
            place["id"] in excluded
            or name in excluded_names
            or explicitly_excluded(place, preferences.custom_request)
        ):
            reason = "explicit exclusion"
        else:
            distance = distance_km(CITY_CENTER, place)
            place["scope"] = "city" if distance <= CITY_RADIUS_KM else "day_trip"
            if distance > EXCURSION_RADIUS_KM or (
                place["scope"] == "day_trip" and not allows_day_trips(preferences)
            ):
                reason = "geographic outlier for normal Kochi itinerary"
        if reason:
            logger.info("[FILTER] Removed %s: %s", place.get("name"), reason)
            continue
        seen.add(name)
        valid.append(place)
    logger.info("[FILTER] %s valid candidates remain", len(valid))
    return valid


def geographic_context(places):
    return {
        "distance_method": "Haversine; travel uses approximate road factor and walking/transit speeds",
        "max_leg_km": MAX_LEG_KM,
        "max_day_diameter_km": MAX_DAY_DIAMETER_KM,
        "pairs": [
            {
                "from": a["id"],
                "to": b["id"],
                "km": round(distance_km(a, b), 2),
                "travel_minutes": travel_estimate(a, b)[0],
            }
            for i, a in enumerate(places)
            for b in places[i + 1 :]
        ],
    }


def meal_windows(place):
    metadata = " ".join(
        str(place.get(key, "")) for key in ("tags", "meal_suitability", "name")
    ).lower()
    windows = []
    for term, window in (
        ("breakfast", (540, 660)),
        ("lunch", (690, 900)),
        ("sadya", (690, 900)),
        ("dinner", (1080, 1260)),
    ):
        if term in metadata:
            windows.append(window)
    if windows:
        return windows
    if place.get("category") == "Food" and not any(
        term in metadata for term in ("cafe", "café", "coffee", "tea", "snack", "bakery", "juice")
    ):
        return [(690, 900), (1080, 1260)]
    return []


def meal_start(place, earliest):
    windows = meal_windows(place)
    if not windows:
        return earliest
    return min((max(earliest, start) for start, end in windows if earliest <= end), default=1440)


def minutes(label):
    hour, minute = label.split(":")
    return int(hour) * 60 + int(minute)


def validate_itinerary(attempt, places, preferences):
    """Return typed errors, never partially trusted provider output."""
    try:
        parsed = (
            ai.Itinerary.model_validate_json(attempt)
            if isinstance(attempt, str)
            else ai.Itinerary.model_validate(attempt)
        )
    except (ValueError, TypeError) as exc:
        return None, [{"type": "INVALID_STRUCTURE", "message": str(exc)[:1500]}]
    errors, seen = [], set()
    allowed = {
        p["id"]: p for p in filter_places(places, preferences, preferences.excluded_place_ids)
    }

    def fail(kind, message, place_id=None):
        errors.append({"type": kind, "place_id": place_id, "message": message})

    if [d.day for d in parsed.days] != list(range(1, preferences.days + 1)):
        fail("INVALID_DAYS", "Return every requested day in order, exactly once.")
    for day in parsed.days:
        previous, end, spent, visited = None, 520, 400, []
        for stop in day.stops:
            p = allowed.get(stop.place_id)
            if p is None:
                fail("UNKNOWN_PLACE", "Use only valid shortlisted IDs.", stop.place_id)
                continue
            identity = _normalise_name(p["name"])
            if identity in seen:
                fail("DUPLICATE_PLACE", "A venue may only appear once across the trip.", p["id"])
            seen.add(identity)
            start, finish = minutes(stop.start_time), minutes(stop.end_time)
            travel = travel_estimate(previous, p)[0] if previous else 0
            if start < max(540, end + 20 + travel, p["opens"] * 60) or finish > min(
                1320, p["closes"] * 60
            ):
                fail(
                    "INVALID_TIME",
                    "Respect hours, day window, travel and 20-minute breaks.",
                    p["id"],
                )
            if not p["duration"] <= finish - start <= p["duration"] * 2:
                fail(
                    "INVALID_DURATION",
                    "Visit duration must be between 1 and 2 times the catalog estimate.",
                    p["id"],
                )
            windows = meal_windows(p)
            purpose_window = {
                "breakfast": (540, 660),
                "lunch": (690, 900),
                "dinner": (1080, 1260),
            }.get(stop.purpose.lower())
            if (windows and not any(lo <= start <= hi for lo, hi in windows)) or (
                purpose_window and not purpose_window[0] <= start <= purpose_window[1]
            ):
                fail("INVALID_MEAL_TIME", "Use a suitable meal period for this stop.", p["id"])
            if previous and distance_km(previous, p) > MAX_LEG_KM:
                fail("GEOGRAPHIC_OUTLIER", "Consecutive stops exceed the 20 km leg limit.", p["id"])
            if any(distance_km(other, p) > MAX_DAY_DIAMETER_KM for other in visited):
                fail(
                    "GEOGRAPHIC_OUTLIER",
                    "Day diameter exceeds 25 km; separate distant clusters into days.",
                    p["id"],
                )
            previous, end = p, finish
            visited.append(p)
            spent += p["cost"]
        if spent > preferences.budget:
            fail("BUDGET_EXCEEDED", f"Day {day.day} costs {spent}, including the 400 allowance.")
        target = (
            preferences.stops_per_day
            or {"relaxed": 3, "balanced": 4, "packed": 5}[preferences.pace]
        )
        minimum = min(2, target, len(allowed) // preferences.days)
        if len(day.stops) < minimum:
            fail("TOO_FEW_STOPS", f"Day {day.day} needs at least {minimum} usable stops.")
    if errors:
        logger.info("[VALIDATOR] Failed: %s", errors)
    return parsed, errors


def raw_itinerary(plan):
    return {
        "days": [
            {
                "day": d["day"],
                "theme": d.get("theme", "Local discoveries"),
                "stops": [
                    {
                        "place_id": s["place"]["id"],
                        "start_time": s["start"],
                        "end_time": s["end"],
                        "purpose": s.get("purpose", "visit"),
                    }
                    for s in d["stops"]
                ],
            }
            for d in plan["days"]
        ]
    }


def canonical_days(parsed, places, preferences):
    from datetime import timedelta

    allowed = {p["id"]: p for p in places}
    days = []
    for day in parsed.days:
        stops, previous = [], None
        for stop in day.stops:
            p = allowed[stop.place_id]
            travel, mode = travel_estimate(previous, p) if previous else (0, "start")
            stops.append(
                dict(
                    id=f"d{day.day}-{p['id']}",
                    place=p,
                    start=stop.start_time,
                    end=stop.end_time,
                    purpose=stop.purpose,
                    travel_minutes=travel,
                    travel_mode=mode,
                    completed=False,
                )
            )
            previous = p
        days.append(
            dict(
                day=day.day,
                date=str(preferences.start_date + timedelta(days=day.day - 1)),
                theme=day.theme,
                stops=stops,
            )
        )
    return days


def refresh_totals(plan):
    budget = plan["preferences"]["budget"]
    for day in plan["days"]:
        places = [s["place"] for s in day["stops"]]
        day["area_clustered"] = len(places) > 1 and all(
            distance_km(a, b) <= CLUSTER_DIAMETER_KM
            for i, a in enumerate(places)
            for b in places[i + 1 :]
        )
        day["cost"] = 400 + sum(p["cost"] for p in places)
        day["budget_utilization"] = round(day["cost"] / budget * 100)
        for number, stop in enumerate(day["stops"], 1):
            stop["number"] = number
    plan["total_cost"] = sum(d["cost"] for d in plan["days"])
    plan["budget_utilization"] = round(plan["total_cost"] / (budget * len(plan["days"])) * 100)
    return plan
