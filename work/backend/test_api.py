import pytest
from fastapi.testclient import TestClient

from . import db
from .app import Preferences, app
from .planner import generate_plan


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app) as client:
        yield client


def create_trip(client, **overrides):
    response = client.post(
        "/api/trips",
        json={"days": 2, "budget": 1500, "interests": ["Culture", "Food"], **overrides},
    )
    assert response.status_code == 201, response.text
    return response.json()


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
            assert end <= min(18 * 60, stop["place"]["closes"] * 60)
            previous = end + 20
            ids.append(stop["place"]["id"])
    assert len(ids) == len(set(ids))
    assert plan["total_cost"] == sum(d["cost"] for d in plan["days"])


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


def test_demo_group_request_is_idempotent(client):
    for _ in range(2):
        assert client.put("/api/groups/sunrise", json={"saved": True}).status_code == 200
    group = client.get("/api/groups").json()[0]
    assert group["demo"] is True
    assert group["status"] == "pending"
    assert group["members"] == 3


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


def test_extreme_dates_are_validation_errors(client):
    assert (
        client.post("/api/trips", json={"start_date": "9999-12-31", "days": 3}).status_code == 422
    )
