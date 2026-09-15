from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fastapi.testclient import TestClient

from . import db
from .app import app
from .test_api import create_trip


def signup(client, name):
    credentials = {"email": f"{name}@example.com", "password": "a-long-test-password"}
    assert client.post("/api/auth/signup", json=credentials).status_code == 201
    return credentials


def create_group(client, **changes):
    response = client.post(
        "/api/groups",
        json={
            "name": "Kochi walkers",
            "date": str(date.today()),
            "meeting_point": "Mattancherry Palace entrance",
            "capacity": 2,
            "interests": ["Culture"],
            **changes,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def listed(client):
    return client.get("/api/groups").json()["groups"]


def test_group_owner_membership_survives_login_and_initialization(client):
    credentials = signup(client, "owner")
    group = create_group(client)
    assert group["members"] == 1 and group["joined"] and group["is_owner"]
    assert group["remaining"] == 1
    db.initialize()
    client.post("/api/auth/logout")
    assert client.get("/api/groups").status_code == 401
    client.post("/api/auth/login", json=credentials)
    assert listed(client)[0] == group


def test_concurrent_joins_cannot_exceed_capacity_or_duplicate_members(client):
    signup(client, "owner")
    group = create_group(client)
    with TestClient(app) as first, TestClient(app) as second:
        signup(first, "first")
        signup(second, "second")
        url = f"/api/groups/{group['id']}/membership"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda c: c.put(url), [first, second]))
        assert sorted(r.status_code for r in results) == [200, 409]
        winner = first if results[0].status_code == 200 else second
        loser = second if winner is first else first
        with ThreadPoolExecutor(max_workers=2) as pool:
            retries = list(pool.map(lambda _: winner.put(url), range(2)))
        assert all(r.status_code == 200 for r in retries)
        assert listed(client)[0]["members"] == 2
        assert winner.delete(url).json()["members"] == 1
        assert winner.delete(url).json()["members"] == 1
        assert loser.put(url).json()["members"] == 2
        assert loser.post(f"/api/groups/{group['id']}/close").status_code == 403
        assert (
            loser.patch(f"/api/groups/{group['id']}", json={"name": "Hijacked"}).status_code == 405
        )
        assert listed(client)[0]["name"] == "Kochi walkers"
        assert client.delete(url).status_code == 409
        assert client.post(f"/api/groups/{group['id']}/close").json()["closed"]
        assert loser.delete(url).status_code == 200
        assert loser.put(url).status_code == 409
        assert client.delete(url).json()["members"] == 0


def test_itinerary_sharing_requires_consent_and_ownership(client):
    signup(client, "owner")
    trip = create_trip(client, title="Shared route")
    private = create_group(client)
    assert private["shared_itinerary"] is None
    base = {
        "name": "Route group",
        "date": str(date.today()),
        "capacity": 4,
        "meeting_point": "Public park gate",
        "interests": ["Nature"],
        "itinerary_id": trip["id"],
    }
    assert client.post("/api/groups", json=base).status_code == 422
    shared = create_group(client, itinerary_id=trip["id"], share_itinerary=True)
    snapshot = shared["shared_itinerary"]
    assert set(snapshot) == {"title", "days"}
    assert snapshot["title"] == "Shared route"
    assert set(snapshot["days"][0]) == {"stops"}
    assert all(isinstance(s, str) for d in snapshot["days"] for s in d["stops"])
    client.cookies.clear()
    signup(client, "other")
    assert client.post("/api/groups", json={**base, "share_itinerary": True}).status_code == 404
    assert client.get(f"/api/trips/{trip['id']}").status_code == 404
    public = listed(client)
    assert all("owner" not in g and "itinerary_id" not in g for g in public)
    assert next(g for g in public if g["id"] == shared["id"])["shared_itinerary"] == snapshot


@pytest.mark.parametrize(
    "change",
    [
        {"name": "   "},
        {"capacity": 1},
        {"capacity": 51},
        {"capacity": 2.5},
        {"date": "2020-01-01"},
        {"interests": []},
        {"interests": ["Invalid"]},
        {"meeting_point": " "},
        {"owner": "someone-else"},
    ],
)
def test_invalid_group_inputs(client, change):
    signup(client, "owner")
    payload = {
        "name": "Good group",
        "date": str(date.today()),
        "meeting_point": "Public park",
        "capacity": 3,
        "interests": ["Food"],
        **change,
    }
    assert client.post("/api/groups", json=payload).status_code == 422
    assert listed(client) == []


@pytest.mark.parametrize("travel_type", ["family", "solo", "group"])
def test_travel_type_is_saved_in_planner_preferences(client, travel_type):
    trip = create_trip(client, travel_type=travel_type)
    assert trip["preferences"]["travel_type"] == travel_type
    assert (
        client.get(f"/api/trips/{trip['id']}").json()["preferences"]["travel_type"] == travel_type
    )


def test_unknown_travel_type_rejected(client):
    assert client.post("/api/trips", json={"travel_type": "unknown"}).status_code == 422
