"""Regression coverage for AI discovery, planning, repair and local guarantees."""

import json
from copy import deepcopy

import pytest

from . import ai
from .app import Preferences
from .catalog import BY_ID
from .planner import generate_plan, replace_stop
from .planning_rules import (
    filter_places,
    geographic_context,
    raw_itinerary,
    refresh_totals,
    validate_itinerary,
)


def proposal(*ids):
    return {
        "days": [
            {
                "day": 1,
                "theme": "Waterfront",
                "stops": [
                    {
                        "place_id": id,
                        "start_time": f"{9 + i * 2:02}:00",
                        "end_time": f"{10 + i * 2:02}:00",
                        "purpose": "sightseeing",
                    }
                    for i, id in enumerate(ids)
                ],
            }
        ]
    }


def test_accent_duplicates_and_invalid_geography():
    original = dict(BY_ID["kashi"])
    duplicate = {**original, "id": "duplicate", "name": "kashi art cafe"}
    far = {**BY_ID["nets"], "id": "far", "name": "Muhamma stop", "lat": 9.6, "lng": 76.35}
    invalid = {**BY_ID["nets"], "id": "invalid", "lat": float("nan")}
    prefs = Preferences(days=1)
    assert [p["id"] for p in filter_places([original, duplicate, far, invalid], prefs)] == ["kashi"]
    assert (
        filter_places([far], prefs.model_copy(update={"allow_day_trips": True}))[0]["scope"]
        == "day_trip"
    )


def test_explicit_exclusions_apply_before_planning():
    prefs = Preferences(custom_request="I have already visited Fort Kochi.")
    assert not filter_places([BY_ID["nets"]], prefs)
    prefs = Preferences(custom_request="Avoid Kashi Art Cafe.")
    assert not filter_places([BY_ID["kashi"]], prefs)


@pytest.mark.parametrize(
    "attempt, kind",
    [
        (proposal("invented"), "UNKNOWN_PLACE"),
        (proposal("nets", "nets"), "DUPLICATE_PLACE"),
        ("{broken json", "INVALID_STRUCTURE"),
        ({"days": []}, "INVALID_STRUCTURE"),
    ],
)
def test_reject_invalid_ai(attempt, kind):
    _, errors = validate_itinerary(attempt, [BY_ID["nets"]], Preferences(days=1, stops_per_day=1))
    assert kind in {e["type"] for e in errors}


def test_overlap_duration_budget_and_meals():
    food = {
        **BY_ID["kashi"],
        "id": "restaurant",
        "name": "Lunch restaurant",
        "tags": ["lunch"],
        "opens": 9,
        "cost": 900,
    }
    attempt = proposal("nets", "restaurant")
    attempt["days"][0]["stops"][1].update(start_time="09:30", end_time="09:35", purpose="lunch")
    _, errors = validate_itinerary(attempt, [BY_ID["nets"], food], Preferences(days=1, budget=1000))
    # The individually over-budget venue is rejected before schedule validation.
    assert "UNKNOWN_PLACE" in {e["type"] for e in errors}
    food["cost"] = 500
    attempt["days"][0]["stops"][0]["end_time"] = "10:00"
    _, errors = validate_itinerary(attempt, [BY_ID["nets"], food], Preferences(days=1, budget=1000))
    assert {"INVALID_TIME", "INVALID_DURATION", "INVALID_MEAL_TIME"} <= {e["type"] for e in errors}


def test_geographic_outlier_and_cluster_label():
    far = {**BY_ID["church"], "id": "far", "name": "Remote church", "lat": 10.24, "lng": 76.26}
    prefs = Preferences(days=1, allow_day_trips=True)
    _, errors = validate_itinerary(proposal("nets", "far"), [BY_ID["nets"], far], prefs)
    assert "GEOGRAPHIC_OUTLIER" in {e["type"] for e in errors}
    plan = {
        "preferences": {"budget": 1500},
        "days": [{"stops": [{"place": BY_ID["nets"]}, {"place": far}]}],
    }
    assert refresh_totals(plan)["days"][0]["area_clustered"] is False
    assert [s["number"] for s in plan["days"][0]["stops"]] == [1, 2]


@pytest.mark.parametrize("bad", [proposal("invented"), "{broken"])
def test_one_repair_receives_original_context(monkeypatch, bad):
    prefs = Preferences(
        days=1,
        stops_per_day=1,
        custom_request="Relaxed, local food, not many museums and a good sunset.",
    )
    monkeypatch.setattr(
        ai, "generate_candidates", lambda _: [ai.Candidate(name=BY_ID["nets"]["name"])]
    )
    calls = []

    def plan(preferences, places, geography, **repair):
        calls.append((preferences, places, geography, repair))
        return bad if len(calls) == 1 else json.dumps(proposal("nets"))

    monkeypatch.setattr(ai, "plan_itinerary", plan)
    result = generate_plan(prefs)
    assert result["planning_source"] == "ai_repair"
    assert len(calls) == 2
    assert calls[1][3]["attempted"] == bad
    assert calls[1][3]["errors"]
    assert calls[0][0].custom_request == prefs.custom_request
    assert calls[0][1] == calls[1][1]
    assert len(calls[0][1]) >= 10
    assert calls[0][2]["pairs"]
    assert result["days"][0]["stops"][0]["number"] == 1


def test_bad_repair_falls_back_once(monkeypatch):
    monkeypatch.setattr(ai, "generate_candidates", lambda _: [])
    calls = []

    def bad(*args, **kwargs):
        calls.append(1)
        return proposal("invented")

    monkeypatch.setattr(ai, "plan_itinerary", bad)
    result = generate_plan(Preferences(days=2))
    assert len(calls) == 2
    assert result["planning_source"] == "fallback"
    places = [s["place"] for d in result["days"] for s in d["stops"]]
    assert not validate_itinerary(raw_itinerary(result), places, Preferences(days=2))[1]


def test_api_failure_and_replacement_preserve_other_days(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ai.GeminiUnavailableError("offline")

    monkeypatch.setattr(ai, "generate_candidates", unavailable)
    monkeypatch.setattr(ai, "plan_itinerary", unavailable)
    prefs = Preferences(days=2, budget=2000)
    plan = generate_plan(prefs)
    original = deepcopy(plan)
    selected = plan["days"][0]["stops"][0]
    revised = replace_stop(plan, selected, prefs, {selected["place"]["id"]})
    assert plan == original
    assert revised["days"][1] == plan["days"][1]
    assert revised["days"][0]["stops"][0]["place"]["id"] != selected["place"]["id"]
    assert len(revised["days"][0]["stops"]) == len(plan["days"][0]["stops"])


def test_distance_context_uses_catalog_coordinates():
    context = geographic_context([BY_ID["nets"], BY_ID["church"]])
    assert 0 < context["pairs"][0]["km"] < 2
    assert context["pairs"][0]["travel_minutes"] >= 10


def test_total_budget_and_multiday_duplicates():
    places = [{**BY_ID[id], "cost": 400} for id in ("nets", "church")]
    _, errors = validate_itinerary(
        proposal("nets", "church"), places, Preferences(days=1, budget=1000)
    )
    assert "BUDGET_EXCEEDED" in {e["type"] for e in errors}
    attempted = proposal("nets")
    second = deepcopy(attempted["days"][0])
    second["day"] = 2
    attempted["days"].append(second)
    _, errors = validate_itinerary(attempted, places, Preferences(days=2, stops_per_day=1))
    assert "DUPLICATE_PLACE" in {e["type"] for e in errors}


def test_saved_custom_request_and_remove_numbering(client):
    response = client.post(
        "/api/trips",
        json={"days": 1, "custom_request": "Relaxed local food and sunset", "stops_per_day": 4},
    )
    assert response.status_code == 201
    plan = response.json()
    removed = plan["days"][0]["stops"][1]["id"]
    response = client.patch(
        f"/api/trips/{plan['id']}", json={"action": "remove", "stop_id": removed}
    )
    assert response.status_code == 200
    stored = client.get(f"/api/trips/{plan['id']}").json()
    assert stored["preferences"]["custom_request"] == "Relaxed local food and sunset"
    assert [s["number"] for s in stored["days"][0]["stops"]] == [1, 2, 3]
    assert all(s["id"] != removed for s in stored["days"][0]["stops"])


def test_planning_prompt_contains_preferences_and_local_facts(monkeypatch):
    captured = {}

    def request(prompt, schema):
        captured.update(prompt=prompt, schema=schema)
        return json.dumps(proposal("nets"))

    monkeypatch.setattr(ai, "_request_json", request)
    prefs = Preferences(custom_request="Relaxed, local food, not many museums, sunset")
    places = [BY_ID["nets"], BY_ID["kashi"]]
    ai.plan_itinerary(prefs, places, geographic_context(places))
    assert captured["prompt"]["traveller_preferences"]["custom_request"] == prefs.custom_request
    assert captured["prompt"]["candidate_places"][0]["lat"] == BY_ID["nets"]["lat"]
    assert "opening hours" in captured["prompt"]["task"]
    assert "sunset" in captured["prompt"]["task"]
    assert captured["schema"]["additionalProperties"] is False


def test_explicit_day_trip_permission_is_required():
    from .planning_rules import allows_day_trips

    assert allows_day_trips(Preferences(custom_request="Include a day trip"))
    assert not allows_day_trips(Preferences(custom_request="Avoid day trips"))
    assert not allows_day_trips(Preferences(custom_request="I don't want day trips"))


def test_museum_exclusion_does_not_turn_soft_preferences_into_hard_rules():
    from .planning_rules import explicitly_excluded

    museum = {**BY_ID["nets"], "name": "Local Museum"}
    assert explicitly_excluded(museum, "I don't want museums")
    assert not explicitly_excluded(museum, "Not many museums, please")
