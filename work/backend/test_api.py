import json

import httpx
import pytest

from . import db
from .app import Preferences
from .catalog import BY_ID, PLACES, REGIONS
from .planner import generate_plan


def create_trip(client, **overrides):
    response = client.post(
        "/api/trips",
        json={"days": 2, "budget": 1500, "interests": ["Culture", "Food"], **overrides},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_same_origin_production_mutation_is_allowed(client):
    response = client.put(
        "/api/bookmarks/slow-kochi",
        json={"saved": True},
        headers={
            "Origin": "https://roam-kochi.onrender.com",
            "Host": "roam-kochi.onrender.com",
        },
    )
    assert response.status_code == 200


def test_cross_origin_mutation_is_rejected(client):
    response = client.put(
        "/api/bookmarks/slow-kochi",
        json={"saved": True},
        headers={"Origin": "https://malicious.example"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ["http://[invalid", "ftp://testserver"])
def test_invalid_origin_is_rejected(client, origin):
    response = client.put(
        "/api/bookmarks/slow-kochi",
        json={"saved": True},
        headers={"Origin": origin},
    )
    assert response.status_code == 403


def test_unknown_api_route_is_not_masked_by_frontend(client):
    assert client.get("/api/does-not-exist").status_code == 404


@pytest.mark.parametrize("days", [1, 2, 3])
@pytest.mark.parametrize("budget", [500, 1500, 5000])
@pytest.mark.parametrize("pace", ["relaxed", "balanced", "packed"])
def test_plan_respects_days_budget_hours_and_unique_stops(days, budget, pace):
    plan = generate_plan(Preferences(days=days, budget=budget, pace=pace))
    assert len(plan["days"]) == days
    ids = []
    for day in plan["days"]:
        assert day["stops"]
        assert day["cost"] <= budget
        previous = 9 * 60
        for stop in day["stops"]:
            start = sum(
                x * factor for x, factor in zip(map(int, stop["start"].split(":")), [60, 1])
            )
            end = sum(x * factor for x, factor in zip(map(int, stop["end"].split(":")), [60, 1]))
            assert start >= previous + stop["travel_minutes"]
            assert start >= stop["place"]["opens"] * 60
            assert end <= min(22 * 60, stop["place"]["closes"] * 60)
            previous = end + 20
            ids.append(stop["place"]["id"])
    assert len(ids) == len(set(ids))
    assert plan["total_cost"] == sum(d["cost"] for d in plan["days"])


@pytest.mark.parametrize("stops_per_day", [3, 5, 7])
def test_selected_stops_per_day_reaches_trip_creation(client, stops_per_day):
    trip = create_trip(
        client,
        days=1,
        budget=1500,
        stops_per_day=stops_per_day,
    )

    assert len(trip["days"][0]["stops"]) == stops_per_day
    assert trip["preferences"]["stops_per_day"] == stops_per_day


def test_twenty_custom_stops_per_day_is_accepted():
    assert Preferences(stops_per_day=20).stops_per_day == 20


def test_explicit_count_reserves_time_for_short_visits(monkeypatch):
    from . import planner

    places = [
        {**BY_ID["nets"], "id": f"short-{i}", "name": f"Short visit {i}",
         "duration": 15, "opens": 9, "closes": 22}
        for i in range(16)
    ]
    places.insert(0, {**places[0], "id": "long", "name": "Long visit", "duration": 180})
    monkeypatch.setattr(planner, "PLACES", places)
    monkeypatch.setattr(planner, "BY_ID", {p["id"]: p for p in places})
    plan = generate_plan(Preferences(days=1, budget=4000, stops_per_day=16), allow_ai=False)
    assert len(plan["days"][0]["stops"]) == 16
    assert "long" not in {s["place"]["id"] for s in plan["days"][0]["stops"]}


def test_shortfall_reports_requested_count_even_when_catalog_is_small():
    plan = generate_plan(
        Preferences(days=1, budget=4000, stops_per_day=16, areas=["vyttila"]),
        allow_ai=False,
    )
    count = len(plan["days"][0]["stops"])
    assert any(f"scheduled {count} of 16 requested stops" in warning for warning in plan["warnings"])


def test_planner_schedules_lulu_only_once_across_catalog_aliases():
    plan = generate_plan(
        Preferences(days=2, budget=2000, stops_per_day=5, areas=["edappally"]),
        requested=["lulu", "lulu_mall"],
    )
    stops = [s for day in plan["days"] for s in day["stops"]]
    assert sum(s["place"]["id"] in {"lulu", "lulu_mall"} for s in stops) == 1


@pytest.mark.parametrize("excluded_id", ["lulu", "lulu_mall"])
def test_excluding_lulu_excludes_its_other_catalog_id(excluded_id):
    plan = generate_plan(
        Preferences(days=1, budget=2000, stops_per_day=5, areas=["edappally"]),
        excluded={excluded_id},
    )
    assert not {"lulu", "lulu_mall"} & {
        s["place"]["id"] for day in plan["days"] for s in day["stops"]
    }


@pytest.mark.parametrize("stops_per_day", [0, 21])
def test_custom_stops_per_day_must_be_between_one_and_twenty(client, stops_per_day):
    response = client.post("/api/trips", json={"stops_per_day": stops_per_day})

    assert response.status_code == 422


def test_catalog_covers_citywide_kochi_regions():
    supported = {region["id"] for region in REGIONS}
    represented = {place["area"] for place in PLACES}
    assert len(PLACES) >= 30
    assert {"fort-kochi", "edappally", "palarivattom", "vyttila"} <= represented
    assert represented <= supported
    assert all(place["area_name"] for place in PLACES)


def test_area_selection_constrains_and_clusters_the_plan():
    plan = generate_plan(
        Preferences(days=3, budget=2000, interests=["Culture", "Shopping"], areas=["edappally"])
    )
    assert len(plan["days"]) == 3
    assert all(day["stops"] for day in plan["days"])
    assert {stop["place"]["area"] for day in plan["days"] for stop in day["stops"]} == {"edappally"}
    assert all(day["stops"][0]["travel_mode"] == "start" for day in plan["days"])


def test_cross_area_routes_label_local_transit():
    plan = generate_plan(
        Preferences(
            days=1,
            budget=2500,
            pace="packed",
            interests=["Nature", "Hidden gems"],
            areas=["vyttila", "panampilly"],
        )
    )
    assert any(
        stop["travel_mode"] == "local transit" for day in plan["days"] for stop in day["stops"]
    )


def test_large_budget_selects_premium_options_without_exceeding_cap(monkeypatch):
    from . import planner

    # Keep the budget policy test independent of changes to the live place catalog.
    places = [
        {**BY_ID["nets"], "id": f"premium-{i}", "name": f"Premium visit {i}",
         "cost": 3000, "price_tier": "premium", "duration": 60, "opens": 9, "closes": 22}
        for i in range(5)
    ]
    places.append({**BY_ID["nets"], "cost": 0})
    monkeypatch.setattr(planner, "PLACES", places)
    monkeypatch.setattr(planner, "BY_ID", {p["id"]: p for p in places})
    budget = 20000
    plan = generate_plan(
        Preferences(
            days=1,
            budget=budget,
            pace="packed",
        ),
        allow_ai=False,
    )
    assert plan["total_cost"] <= budget
    assert plan["budget_utilization"] >= 70
    assert any(
        stop["place"]["price_tier"] == "premium" for day in plan["days"] for stop in day["stops"]
    )


def test_unknown_area_is_rejected(client):
    assert client.post("/api/trips", json={"areas": ["somewhere-else"]}).status_code == 422


def test_completion_is_idempotent_persists_and_can_be_undone(client):
    trip = create_trip(client)
    stop = trip["days"][0]["stops"][0]["id"]
    url = f"/api/trips/{trip['id']}/stops/{stop}"
    for _ in range(3):
        assert client.put(url, json={"completed": True}).status_code == 200
    assert client.get("/api/me").json()["points"] == 10
    assert client.get(f"/api/trips/{trip['id']}").json()["days"][0]["stops"][0]["completed"]
    assert client.put(url, json={"completed": False}).status_code == 200
    assert client.get("/api/me").json()["points"] == 0


def test_completed_places_are_stored_in_visited_history(client):
    trip = create_trip(client, days=1, stops_per_day=1)
    stop = trip["days"][0]["stops"][0]

    client.put(
        f"/api/trips/{trip['id']}/stops/{stop['id']}", json={"completed": True}
    )

    assert client.get("/api/me").json()["visited_places"] == [stop["place"]["id"]]


def test_new_places_only_excludes_visited_places(client):
    first = create_trip(client, days=1, stops_per_day=1)
    first_stop = first["days"][0]["stops"][0]
    client.put(
        f"/api/trips/{first['id']}/stops/{first_stop['id']}", json={"completed": True}
    )

    fresh = create_trip(client, days=1, stops_per_day=1, include_visited=False)

    assert fresh["days"][0]["stops"][0]["place"]["id"] != first_stop["place"]["id"]
    assert fresh["preferences"]["include_visited"] is False


def test_saved_pre_area_trip_data_is_enriched_on_read(client):
    trip = create_trip(client)
    with db.connect() as connection:
        row = connection.execute("SELECT plan FROM trips WHERE id=?", (trip["id"],)).fetchone()
        plan = json.loads(row["plan"])
        for day in plan["days"]:
            for stop in day["stops"]:
                stop.pop("travel_mode", None)
                stop["place"].pop("area", None)
                stop["place"].pop("area_name", None)
        connection.execute(
            "UPDATE trips SET plan=? WHERE id=?",
            (json.dumps(plan), trip["id"]),
        )
    restored = client.get(f"/api/trips/{trip['id']}").json()
    first = restored["days"][0]["stops"][0]
    assert first["travel_mode"] == "walk"
    assert first["place"]["area"]
    assert first["place"]["area_name"]


def test_unstarted_saved_trip_with_duplicate_venue_aliases_is_repaired(client):
    trip = create_trip(client, days=1, budget=2000, stops_per_day=5)
    with db.connect() as connection:
        row = connection.execute(
            "SELECT plan FROM trips WHERE id=?", (trip["id"],)
        ).fetchone()
        plan = json.loads(row["plan"])
        duplicate_ids = ["kashi", "kashi_art_cafe"]
        for stop, place_id in zip(plan["days"][0]["stops"][:2], duplicate_ids):
            stop["id"] = f"d1-{place_id}"
            stop["place"] = BY_ID[place_id]
        connection.execute(
            "UPDATE trips SET plan=? WHERE id=?",
            (json.dumps(plan), trip["id"]),
        )

    restored = client.get(f"/api/trips/{trip['id']}").json()
    restored_ids = [stop["place"]["id"] for stop in restored["days"][0]["stops"]]

    assert len(restored_ids) == 5
    assert sum(place_id in {"kashi", "kashi_art_cafe"} for place_id in restored_ids) == 1
    with db.connect() as connection:
        stored = json.loads(
            connection.execute(
                "SELECT plan FROM trips WHERE id=?", (trip["id"],)
            ).fetchone()["plan"]
        )
    assert [stop["place"]["id"] for stop in stored["days"][0]["stops"]] == restored_ids


def test_day_bonus_awarded_once(client):
    trip = create_trip(client, days=1)
    for stop in trip["days"][0]["stops"]:
        client.put(f"/api/trips/{trip['id']}/stops/{stop['id']}", json={"completed": True})
    profile = client.get("/api/me").json()
    assert profile["points"] == len(trip["days"][0]["stops"]) * 10 + 25
    assert "Trip storyteller" in profile["badges"]


def test_guest_cannot_read_or_edit_another_guests_trip(client):
    trip = create_trip(client)
    client.cookies.clear()
    assert client.get(f"/api/trips/{trip['id']}").status_code == 404
    assert (
        client.put(
            f"/api/trips/{trip['id']}/stops/{trip['days'][0]['stops'][0]['id']}",
            json={"completed": True},
        ).status_code
        == 404
    )
    assert client.get("/api/me").json()["trips"] == []


def test_invalid_stop_and_impossible_constraints(client):
    trip = create_trip(client)
    assert (
        client.put(f"/api/trips/{trip['id']}/stops/missing", json={"completed": True}).status_code
        == 404
    )
    assert client.post("/api/trips", json={"budget": 200}).status_code == 422
    assert client.post("/api/trips", json={"min_slh": 100}).status_code == 422
    assert client.post("/api/trips", json={"days": 7}).status_code == 422
    assert client.post("/api/trips", json={"interests": ["Invalid"]}).status_code == 422


def test_bookmarks_are_durable_and_private(client):
    assert client.put("/api/bookmarks/slow-kochi", json={"saved": True}).status_code == 200
    assert client.get("/api/me").json()["saved"] == ["slow-kochi"]
    client.cookies.clear()
    assert client.get("/api/me").json()["saved"] == []


def test_drafts_preserve_notes_and_reject_unknown_places(client):
    notes = "We visited Chinese Fishing Nets and the imaginary Moon Palace."
    response = client.post("/api/drafts", json={"title": "My Kochi story", "notes": notes})
    assert response.status_code == 201
    draft = response.json()
    assert draft["notes"] == notes
    assert draft["place_ids"] == ["nets"]
    assert (
        client.put(
            f"/api/drafts/{draft['id']}",
            json={
                "title": "Updated story",
                "notes": notes,
                "place_ids": ["moon-palace"],
            },
        ).status_code
        == 422
    )
    client.cookies.clear()
    assert (
        client.put(
            f"/api/drafts/{draft['id']}",
            json={"title": "Updated story", "notes": notes, "place_ids": ["nets"]},
        ).status_code
        == 404
    )


def test_foreign_origin_cannot_mutate(client):
    assert (
        client.post("/api/trips", json={}, headers={"Origin": "https://example.com"}).status_code
        == 403
    )


def test_stop_removal_updates_cost_and_preserves_other_stops(client):
    trip = create_trip(client)
    selected = trip["days"][0]["stops"][0]
    response = client.patch(
        f"/api/trips/{trip['id']}", json={"stop_id": selected["id"], "action": "remove"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert len(updated["days"][0]["stops"]) == len(trip["days"][0]["stops"]) - 1
    assert updated["total_cost"] == trip["total_cost"] - selected["place"]["cost"]
    assert updated["budget_utilization"] == round(
        updated["total_cost"] / (1500 * len(updated["days"])) * 100
    )
    assert selected["id"] not in [s["id"] for d in updated["days"] for s in d["stops"]]


def test_replacement_reschedules_without_the_excluded_place(client):
    trip = create_trip(client)
    selected = trip["days"][0]["stops"][0]
    response = client.patch(
        f"/api/trips/{trip['id']}",
        json={"stop_id": selected["id"], "action": "replace"},
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert selected["place"]["id"] not in [
        s["place"]["id"] for d in updated["days"] for s in d["stops"]
    ]
    assert all(d["cost"] <= 1500 for d in updated["days"])


def test_editing_cannot_destroy_existing_progress(client):
    trip = create_trip(client)
    stop = trip["days"][0]["stops"][0]
    client.put(f"/api/trips/{trip['id']}/stops/{stop['id']}", json={"completed": True})
    response = client.patch(
        f"/api/trips/{trip['id']}", json={"stop_id": stop["id"], "action": "replace"}
    )
    assert response.status_code == 409
    assert client.get("/api/me").json()["points"] == 10


def test_story_to_followable_trip_preserves_attribution(client):
    draft = client.post(
        "/api/drafts",
        json={
            "title": "A slow Kochi morning",
            "notes": "Chinese Fishing Nets followed by Kashi Art Café made a lovely morning.",
        },
    ).json()
    response = client.post("/api/draft-trips", json={"draft_id": draft["id"], "days": 1})
    assert response.status_code == 201, response.text
    trip = response.json()
    assert trip["source_draft"] == draft["id"]
    assert trip["title"] == draft["title"]
    assert {"nets", "kashi"} <= {s["place"]["id"] for d in trip["days"] for s in d["stops"]}


def test_ai_failure_saves_original_notes_with_honest_fallback(client, monkeypatch):
    from . import ai

    def fail(_):
        raise ValueError("Unavailable")

    monkeypatch.setattr(ai, "extract_story", fail)
    notes = "Chinese Fishing Nets was the first stop on our memorable trip."
    response = client.post(
        "/api/drafts", json={"title": "My story", "notes": notes, "use_ai": True}
    )
    assert response.status_code == 201
    assert response.json()["notes"] == notes
    assert response.json()["method"] == "Catalog matching · AI unavailable"


def test_gemini_story_extraction_uses_structured_output(monkeypatch):
    from . import ai

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": '{"place_ids":["chinese_fishing_nets"],"summary":"A waterfront Kochi day.","unresolved":[]}',
                            }
                        ],
                    }
                ],
            }

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 30

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, body=json)
            return FakeResponse()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai.httpx, "Client", FakeClient)
    result = ai.extract_story("We spent the morning at the Chinese Fishing Nets.")
    assert result.place_ids == ["chinese_fishing_nets"]
    assert captured["url"].endswith("/v1beta/interactions")
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["body"]["response_format"]["mime_type"] == "application/json"


def test_trip_uses_ai_candidate_and_ranking_pipeline_when_available(monkeypatch):
    from . import ai

    monkeypatch.setattr(
        ai,
        "generate_candidates",
        lambda _: [ai.Candidate(name="Chinese Fishing Nets", category="Nature", reason="Waterfront")],
    )
    monkeypatch.setattr(ai, "rerank_places", lambda _, places: [places[0]["id"]])

    plan = generate_plan(Preferences(days=1, budget=1500, stops_per_day=1))

    assert plan["recommendation_mode"] == "ai"


@pytest.mark.parametrize("failure", ["missing", "invalid", "quota", "timeout", "malformed"])
def test_trip_falls_back_for_all_gemini_failures(monkeypatch, failure):
    from . import ai

    if failure == "missing":
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    elif failure == "malformed":
        monkeypatch.setattr(ai, "generate_candidates", lambda _: (_ for _ in ()).throw(ai.GeminiUnavailableError("bad JSON")))
    else:
        error = httpx.TimeoutException("timeout") if failure == "timeout" else httpx.HTTPStatusError(
            failure, request=httpx.Request("POST", "https://example.test"), response=httpx.Response(429 if failure == "quota" else 401)
        )
        monkeypatch.setattr(ai, "generate_candidates", lambda _: (_ for _ in ()).throw(error))

    plan = generate_plan(Preferences(days=1, budget=1500, stops_per_day=1))

    assert plan["recommendation_mode"] == "fallback"
    assert plan["days"][0]["stops"]


def test_extreme_dates_are_validation_errors(client):
    assert (
        client.post("/api/trips", json={"start_date": "9999-12-31", "days": 3}).status_code == 422
    )


def test_account_login_role_and_persistence(client):
    credentials = {"email": "Traveler@Example.com", "password": "my-secret-password"}
    response = client.post("/api/auth/signup", json=credentials)
    assert response.status_code == 201
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/me").json()["user"]["role_selected"] == 0
    assert client.put("/api/auth/role", json={"role": "tourist"}).status_code == 200
    trip = create_trip(client)
    old_token = client.cookies.get("roam_auth")
    with db.connect() as connection:
        account = connection.execute("SELECT * FROM accounts").fetchone()
        assert account["email"] == "traveler@example.com"
        assert credentials["password"] not in account["password_hash"]
        assert account["role"] == "tourist"
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/me").json()["user"] is None
    assert client.get(f"/api/trips/{trip['id']}").status_code == 404
    client.cookies.set("roam_auth", old_token)
    assert client.get("/api/me").json()["user"] is None
    client.cookies.clear()
    wrong = {**credentials, "password": "wrong-password"}
    assert client.post("/api/auth/login", json=wrong).status_code == 401
    assert client.get("/api/me").json()["user"] is None
    assert client.post("/api/auth/login", json=credentials).status_code == 200
    profile = client.get("/api/me").json()
    assert profile["user"]["role_selected"] == 0
    assert profile["trips"][0]["id"] == trip["id"]
    assert client.put("/api/auth/role", json={"role": "local"}).status_code == 200
    assert client.get("/api/me").json()["user"]["role"] == "local"
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/signup", json={**credentials, "email": "other@example.com"}
        ).status_code
        == 201
    )
    assert client.get(f"/api/trips/{trip['id']}").status_code == 404


def test_account_validation_and_expiry(client):
    credentials = {"email": "person@example.com", "password": "long-password"}
    assert client.put("/api/auth/role", json={"role": "local"}).status_code == 401
    assert client.post("/api/auth/signup", json={**credentials, "email": "bad"}).status_code == 422
    assert (
        client.post("/api/auth/signup", json={**credentials, "password": "short"}).status_code
        == 422
    )
    assert client.post("/api/auth/signup", json=credentials).status_code == 201
    assert (
        client.post(
            "/api/auth/signup", json={**credentials, "email": "PERSON@example.com"}
        ).status_code
        == 409
    )
    assert client.put("/api/auth/role", json={"role": "admin"}).status_code == 422
    with db.connect() as connection:
        connection.execute("UPDATE account_sessions SET expires_at=0")
    assert client.get("/api/me").json()["user"] is None
    assert client.put("/api/auth/role", json={"role": "local"}).status_code == 401


def test_login_attempts_are_limited(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "missing@example.com", "password": "incorrect-password"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "incorrect-password"},
        ).status_code
        == 429
    )


def test_successful_login_does_not_exhaust_email_attempts(client):
    credentials = {"email": "returning@example.com", "password": "long-password"}
    assert client.post("/api/auth/signup", json=credentials).status_code == 201
    for _ in range(11):
        assert client.post("/api/auth/login", json=credentials).status_code == 200
