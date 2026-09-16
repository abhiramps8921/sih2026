from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from . import contributions, db
from .app import Preferences, app
from .planner import _eligible_places


def signup(client, name):
    assert (
        client.post(
            "/api/auth/signup",
            json={"email": f"{name}@example.com", "password": "long-test-password"},
        ).status_code
        == 201
    )
    assert client.put("/api/auth/role", json={"role": "tourist"}).status_code == 200


def payload(**changes):
    return {
        "safety": 4,
        "legitimacy": 5,
        "hygiene": 3,
        "visit_date": str(date.today()),
        "personal_experience": True,
        **changes,
    }


def save(client, place="nets", **changes):
    response = client.put(f"/api/places/{place}/contribution", json=payload(**changes))
    assert response.status_code == 200, response.text
    return response.json()


def place(client, id="nets"):
    return next(p for p in client.get("/api/places").json() if p["id"] == id)


def test_auth_role_ownership_and_persistence(client):
    url = "/api/places/nets/contribution"
    for method in ["get", "put", "delete"]:
        response = getattr(client, method)(url, **({"json": payload()} if method == "put" else {}))
        assert response.status_code == 401
    client.post(
        "/api/auth/signup", json={"email": "owner@example.com", "password": "long-test-password"}
    )
    assert client.put(url, json=payload()).status_code == 403
    client.put("/api/auth/role", json={"role": "local"})
    saved = save(client)
    db.initialize()
    assert client.get(url).json()["contribution"] == saved
    with TestClient(app) as other:
        signup(other, "other")
        assert other.get(url).json()["contribution"] is None
        other.delete(url)
        save(other, safety=1)
    assert client.get(url).json()["contribution"] == saved


@pytest.mark.parametrize(
    "changes",
    [
        {"safety": None},
        {"safety": 0},
        {"hygiene": 6},
        {"safety": True},
        {"safety": 2.5},
        {"safety": None, "legitimacy": None, "hygiene": None, "tip": "  "},
        {"visit_date": str(date.today() + timedelta(days=1))},
        {"visit_date": "2026-02-30"},
        {"visit_date": 123},
        {"tip": "x" * 501},
        {"tip_category": "advertising"},
        {"personal_experience": False},
        {"tip": "https://one.test https://two.test"},
        {"tip": "a" * 20},
        {"owner": "someone-else"},
    ],
)
def test_invalid_inputs(client, changes):
    signup(client, "invalid")
    assert client.put("/api/places/nets/contribution", json=payload(**changes)).status_code == 422


def test_unknown_place_and_tip_only(client):
    signup(client, "tips")
    assert client.put("/api/places/unknown/contribution", json=payload()).status_code == 404
    saved = save(
        client,
        safety=None,
        legitimacy=None,
        hygiene=None,
        tip="Visit early for a quieter walk.",
        tip_category="best time",
    )
    assert saved["safety"] is None
    assert place(client)["community_slh"] is None
    public = client.get("/api/places/nets/tips").json()["tips"]
    assert public[0]["tip"] == saved["tip"]
    assert "owner" not in public[0] and "email" not in public[0]


def test_threshold_edit_delete_saved_trip_and_planner(client):
    signup(client, "first")
    trip_response = client.post("/api/trips", json={"days": 1, "template_id": "slow-kochi"})
    assert trip_response.status_code == 201
    trip = trip_response.json()
    stop_id = trip["days"][0]["stops"][0]["place"]["id"]
    before = place(client, stop_id)
    first = save(client, stop_id, safety=1, legitimacy=1, hygiene=1)
    save(client, stop_id, safety=1, legitimacy=1, hygiene=1)
    early = place(client, stop_id)
    assert early["community_slh"]["reviews"] == 1
    assert early["slh"] == before["slh"]
    with TestClient(app) as second, TestClient(app) as third:
        signup(second, "second")
        signup(third, "third")
        save(second, stop_id, safety=1, legitimacy=1, hygiene=1)
        save(third, stop_id, safety=1, legitimacy=1, hygiene=1)
        current = place(client, stop_id)
        assert current["slh_source"] == "community"
        assert current["slh"]["safety"] == 1 and current["slh"]["reviews"] == 3
        assert current["demo_slh"] == before["demo_slh"]
        for url in [f"/api/trips/{trip['id']}", "/api/me"]:
            response = client.get(url).json()
            hydrated = response["trips"][0] if url == "/api/me" else response
            assert hydrated["days"][0]["stops"][0]["place"]["slh"] == current["slh"]
        with db.connect() as connection:
            eligible = _eligible_places(
                Preferences(min_slh=50), set(), contributions.current_places(connection)
            )
        assert stop_id not in {p["id"] for p in eligible}
        updated = save(client, stop_id, safety=4, legitimacy=4, hygiene=4)
        assert updated["id"] == first["id"]
        assert place(client, stop_id)["slh"]["safety"] == 2
        third.delete(f"/api/places/{stop_id}/contribution")
        assert place(client, stop_id)["slh"] == before["slh"]


def test_reports_deduplicate_hide_and_do_not_change_rating(client):
    signup(client, "author")
    saved = save(client, tip="<script>alert(1)</script> Bring water.")
    url = f"/api/tips/{saved['id']}/reports"
    assert client.post(url).status_code == 422
    with TestClient(app) as reporter:
        assert reporter.post(url).status_code == 401
        for index in range(3):
            if index:
                reporter.post("/api/auth/logout")
            signup(reporter, f"reporter{index}")
            assert reporter.post(url).status_code == 200
            assert reporter.post(url).status_code == 200
            assert client.get("/api/places/nets/tips").json()["tips"] == []
    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM tip_reports").fetchone()[0] == 3
    own = client.get("/api/places/nets/contribution").json()["contribution"]
    assert own["tip_status"] == "hidden" and own["rating_status"] == "published"
    assert place(client)["community_slh"]["reviews"] == 1
    assert save(client, tip="Edited tip stays hidden.")["tip_status"] == "hidden"
    client.delete("/api/places/nets/contribution")
    assert place(client)["community_slh"] is None


def test_no_demo_stays_unrated_until_threshold(client):
    target = next(p["id"] for p in client.get("/api/places").json() if p["slh_source"] == "unrated")
    signup(client, "no-demo")
    save(client, target)
    assert place(client, target)["slh_source"] == "unrated"
    assert place(client, target)["community_slh"]["reviews"] == 1


def test_self_reported_visit_context(client):
    signup(client, "visitor")
    trip = client.post("/api/trips", json={"days": 1}).json()
    stop = trip["days"][0]["stops"][0]
    url = f"/api/places/{stop['place']['id']}/contribution"
    assert not client.get(url).json()["self_reported_visit"]
    client.put(f"/api/trips/{trip['id']}/stops/{stop['id']}", json={"completed": True})
    assert client.get(url).json()["self_reported_visit"]
