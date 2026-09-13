import json
import secrets
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from . import ai, db
from .catalog import BY_ID, PLACES, REGION_IDS, REGIONS, TEMPLATE_STOPS
from .planner import generate_plan


@asynccontextmanager
async def lifespan(app):
    db.initialize()
    yield


app = FastAPI(title="Roam local travel API", lifespan=lifespan)


@app.middleware("http")
async def guest_session(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = {
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
        }
        if origin and origin not in allowed:
            from starlette.responses import JSONResponse

            return JSONResponse(
                {"detail": "This local app only accepts same-site changes."},
                status_code=403,
            )
    session = request.cookies.get("roam_session", "")
    with db.connect() as connection:
        exists = connection.execute("SELECT id FROM sessions WHERE id = ?", (session,)).fetchone()
        if not exists:
            session = secrets.token_urlsafe(32)
            connection.execute("INSERT INTO sessions(id) VALUES (?)", (session,))
    request.state.owner = session
    response = await call_next(request)
    if not exists:
        response.set_cookie(
            "roam_session",
            session,
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,
        )
    response.headers["Cache-Control"] = "no-store"
    return response


class Preferences(BaseModel):
    days: int = Field(default=2, ge=1, le=3)
    budget: int = Field(default=1500, ge=500, le=20000)
    interests: list[Literal["Food", "Culture", "Nature", "Art", "Hidden gems", "Shopping"]] = Field(
        default_factory=lambda: ["Culture", "Food"], max_length=6
    )
    areas: list[str] = Field(default_factory=list, max_length=12)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    start_date: date = Field(default_factory=date.today)
    min_slh: int = Field(default=0, ge=0, le=100)
    template_id: str | None = Field(default=None, max_length=80)
    title: str = Field(default="", max_length=100)

    @field_validator("start_date")
    @classmethod
    def reasonable_date(cls, value):
        if value.year > 2100 or value.year < 2020:
            raise ValueError("Choose a trip date between 2020 and 2100.")
        return value

    @field_validator("areas")
    @classmethod
    def known_areas(cls, value):
        if any(area not in REGION_IDS for area in value):
            raise ValueError("Choose areas from the supported Kochi region list.")
        return list(dict.fromkeys(value))


class Completion(BaseModel):
    completed: bool


class BookmarkChange(BaseModel):
    saved: bool


class DraftInput(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    notes: str = Field(min_length=20, max_length=10000)
    use_ai: bool = False


class DraftUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    notes: str = Field(min_length=20, max_length=10000)
    place_ids: list[str] = Field(max_length=len(PLACES))


class EditTrip(BaseModel):
    stop_id: str = Field(min_length=1, max_length=100)
    action: Literal["replace", "remove"]


class DraftTrip(Preferences):
    draft_id: str = Field(min_length=1, max_length=100)


def load_trip(connection, trip_id, owner):
    row = connection.execute(
        "SELECT plan FROM trips WHERE id=? AND owner=?", (trip_id, owner)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Trip not found in your session.")
    plan = json.loads(row["plan"])
    completed = {
        r["stop"]
        for r in connection.execute("SELECT stop FROM completions WHERE trip=?", (trip_id,))
    }
    for day in plan["days"]:
        for stop in day["stops"]:
            current_place = BY_ID.get(stop["place"]["id"])
            if current_place:
                stop["place"] = {**current_place, **stop["place"]}
            stop.setdefault("travel_mode", "walk")
            stop["completed"] = stop["id"] in completed
    plan["id"] = trip_id
    return plan


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/places")
def places():
    return PLACES


@app.get("/api/config")
def config():
    return {
        "ai_enabled": ai.enabled(),
        "ai_provider": "Gemini",
        "city": "Kochi",
        "social_mode": "demo",
    }


@app.get("/api/regions")
def regions():
    return REGIONS


@app.get("/api/me")
def me(request: Request):
    with db.connect() as connection:
        ids = [
            r["id"]
            for r in connection.execute(
                "SELECT id FROM trips WHERE owner=? ORDER BY created_at DESC",
                (request.state.owner,),
            )
        ]
        trips = [load_trip(connection, id, request.state.owner) for id in ids]
        count = sum(s["completed"] for t in trips for d in t["days"] for s in d["stops"])
        completed_days = sum(
            all(s["completed"] for s in d["stops"]) for t in trips for d in t["days"]
        )
        badges = []
        if count:
            badges.append("First footsteps")
        if completed_days:
            badges.append("Day well spent")
        if any(all(s["completed"] for d in t["days"] for s in d["stops"]) for t in trips):
            badges.append("Trip storyteller")
        saved = [
            r["template"]
            for r in connection.execute(
                "SELECT template FROM bookmarks WHERE owner=?", (request.state.owner,)
            )
        ]
        return dict(
            points=count * 10 + completed_days * 25,
            completed=count,
            badges=badges,
            saved=saved,
            trips=trips,
        )


@app.post("/api/trips", status_code=201)
def create_trip(preferences: Preferences, request: Request):
    if preferences.template_id and preferences.template_id not in TEMPLATE_STOPS:
        raise HTTPException(422, "Choose an available itinerary template.")
    try:
        plan = generate_plan(preferences)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    id = secrets.token_urlsafe(12)
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO trips(id,owner,plan) VALUES (?,?,?)",
            (id, request.state.owner, json.dumps(plan)),
        )
    return {**plan, "id": id}


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: str, request: Request):
    with db.connect() as connection:
        return load_trip(connection, trip_id, request.state.owner)


@app.patch("/api/trips/{trip_id}")
def edit_trip(trip_id: str, change: EditTrip, request: Request):
    with db.connect() as connection:
        plan = load_trip(connection, trip_id, request.state.owner)
        all_stops = [s for d in plan["days"] for s in d["stops"]]
        if any(s["completed"] for s in all_stops):
            raise HTTPException(
                409,
                "Undo completed stops before changing this schedule. Your progress has been preserved.",
            )
        selected = next((s for s in all_stops if s["id"] == change.stop_id), None)
        if selected is None:
            raise HTTPException(404, "Stop not found in this trip.")
        preferences = Preferences(**plan["preferences"])
        if change.action == "replace":
            excluded = set(plan.get("excluded_places", [])) | {selected["place"]["id"]}
            try:
                revised = generate_plan(
                    preferences,
                    excluded=excluded,
                    requested=[s["place"]["id"] for s in all_stops if s["id"] != change.stop_id],
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            old_ids = {s["place"]["id"] for s in all_stops}
            if not any(
                s["place"]["id"] not in old_ids for d in revised["days"] for s in d["stops"]
            ):
                raise HTTPException(
                    422,
                    "No replacement fits these constraints. Try a different stop or keep this plan.",
                )
            revised["excluded_places"] = sorted(excluded)
            plan = revised
        else:
            from .planner import time_label, travel_estimate

            for day in plan["days"]:
                if not any(s["id"] == change.stop_id for s in day["stops"]):
                    continue
                if len(day["stops"]) == 1:
                    raise HTTPException(422, "Keep at least one stop in each day.")
                day["stops"] = [s for s in day["stops"] if s["id"] != change.stop_id]
                previous = None
                clock = 9 * 60
                for stop in day["stops"]:
                    travel, travel_mode = (
                        travel_estimate(previous, stop["place"]) if previous else (0, "start")
                    )
                    start = max(clock + travel, stop["place"]["opens"] * 60)
                    end = start + stop["place"]["duration"]
                    if end > min(22 * 60, stop["place"]["closes"] * 60):
                        raise HTTPException(
                            422,
                            "Removing this stop would make the remaining route infeasible. Your original plan is unchanged.",
                        )
                    stop.update(
                        start=time_label(start),
                        end=time_label(end),
                        travel_minutes=travel,
                        travel_mode=travel_mode,
                    )
                    previous = stop["place"]
                    clock = end + 20
                day["cost"] = 400 + sum(s["place"]["cost"] for s in day["stops"])
                day["budget_utilization"] = round(day["cost"] / plan["preferences"]["budget"] * 100)
            plan["total_cost"] = sum(d["cost"] for d in plan["days"])
            plan["budget_utilization"] = round(
                plan["total_cost"] / (plan["preferences"]["budget"] * len(plan["days"])) * 100
            )
        connection.execute("UPDATE trips SET plan=? WHERE id=?", (json.dumps(plan), trip_id))
    return {**plan, "id": trip_id}


@app.put("/api/trips/{trip_id}/stops/{stop_id}")
def complete(trip_id: str, stop_id: str, change: Completion, request: Request):
    with db.connect() as connection:
        plan = load_trip(connection, trip_id, request.state.owner)
        if not any(s["id"] == stop_id for d in plan["days"] for s in d["stops"]):
            raise HTTPException(404, "Stop not found in this trip.")
        if change.completed:
            connection.execute(
                "INSERT OR IGNORE INTO completions(trip,stop) VALUES (?,?)",
                (trip_id, stop_id),
            )
        else:
            connection.execute(
                "DELETE FROM completions WHERE trip=? AND stop=?", (trip_id, stop_id)
            )
        return load_trip(connection, trip_id, request.state.owner)


@app.put("/api/bookmarks/{template_id}")
def bookmark(template_id: str, change: BookmarkChange, request: Request):
    if template_id not in TEMPLATE_STOPS:
        raise HTTPException(404, "Itinerary not found.")
    with db.connect() as connection:
        if change.saved:
            connection.execute(
                "INSERT OR IGNORE INTO bookmarks VALUES (?,?)",
                (request.state.owner, template_id),
            )
        else:
            connection.execute(
                "DELETE FROM bookmarks WHERE owner=? AND template=?",
                (request.state.owner, template_id),
            )
    return {"saved": change.saved}


@app.post("/api/drafts", status_code=201)
def draft(payload: DraftInput, request: Request):
    found = [
        p["id"]
        for p in PLACES
        if p["name"].lower() in payload.notes.lower() or p["id"] in payload.notes.lower().split()
    ]
    content = dict(
        title=payload.title,
        notes=payload.notes,
        place_ids=found,
        method="Catalog matching · no AI provider connected",
        status="draft",
        notice="Only recognized catalog places were extracted. Review the stops; unrecognized names remain in your original notes.",
    )
    if payload.use_ai:
        try:
            extraction = ai.extract_story(payload.notes)
            content.update(
                place_ids=extraction.place_ids,
                summary=extraction.summary,
                unresolved=extraction.unresolved,
                method="AI-assisted extraction · contributor review required",
                notice="AI matched these places. Review the list and any unresolved names before scheduling.",
            )
        except (ValueError, httpx.HTTPError):
            content.update(
                method="Catalog matching · AI unavailable",
                notice="AI could not finish. Your complete original notes were saved using catalog matching; review recognized places below.",
            )
    id = secrets.token_urlsafe(12)
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO drafts(id,owner,content) VALUES (?,?,?)",
            (id, request.state.owner, json.dumps(content)),
        )
    return {**content, "id": id}


@app.get("/api/drafts")
def drafts(request: Request):
    with db.connect() as connection:
        return [
            {**json.loads(r["content"]), "id": r["id"]}
            for r in connection.execute(
                "SELECT id,content FROM drafts WHERE owner=? ORDER BY created_at DESC",
                (request.state.owner,),
            )
        ]


@app.put("/api/drafts/{draft_id}")
def edit_draft(draft_id: str, payload: DraftUpdate, request: Request):
    if any(id not in BY_ID for id in payload.place_ids):
        raise HTTPException(422, "Choose places from the pilot catalog.")
    with db.connect() as connection:
        row = connection.execute(
            "SELECT content FROM drafts WHERE id=? AND owner=?",
            (draft_id, request.state.owner),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Draft not found.")
        content = {**json.loads(row["content"]), **payload.model_dump()}
        connection.execute(
            "UPDATE drafts SET content=? WHERE id=?", (json.dumps(content), draft_id)
        )
    return {**content, "id": draft_id}


@app.post("/api/draft-trips", status_code=201)
def schedule_draft(payload: DraftTrip, request: Request):
    with db.connect() as connection:
        row = connection.execute(
            "SELECT content FROM drafts WHERE id=? AND owner=?",
            (payload.draft_id, request.state.owner),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Draft not found.")
        content = json.loads(row["content"])
        if not content["place_ids"]:
            raise HTTPException(422, "Select at least one recognized place in your draft first.")
        preferences = Preferences(
            **{**payload.model_dump(exclude={"draft_id"}), "title": content["title"]}
        )
        try:
            plan = generate_plan(preferences, requested=content["place_ids"])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        plan["source_draft"] = payload.draft_id
        id = secrets.token_urlsafe(12)
        connection.execute(
            "INSERT INTO trips(id,owner,plan) VALUES (?,?,?)",
            (id, request.state.owner, json.dumps(plan)),
        )
    return {**plan, "id": id}


GROUPS = [
    dict(
        id="sunrise",
        title="A slow morning in Fort Kochi",
        date="2026-10-03",
        time="09:00",
        place="Chinese Fishing Nets",
        members=3,
        capacity=6,
        tags=["Photography", "Easy pace"],
        host="Ananya",
        initials="AM",
    ),
    dict(
        id="food-walk",
        title="Good food, better company",
        date="2026-10-04",
        time="12:00",
        place="Mattancherry Palace entrance",
        members=4,
        capacity=6,
        tags=["Food", "Culture"],
        host="Meera",
        initials="MK",
    ),
]


@app.get("/api/groups")
def groups(request: Request):
    with db.connect() as connection:
        requests = {
            r["departure"]: r["status"]
            for r in connection.execute(
                "SELECT departure,status FROM group_requests WHERE owner=?",
                (request.state.owner,),
            )
        }
    return [{**g, "status": requests.get(g["id"]), "demo": True} for g in GROUPS]


@app.put("/api/groups/{group_id}")
def join_group(group_id: str, change: BookmarkChange, request: Request):
    if group_id not in {g["id"] for g in GROUPS}:
        raise HTTPException(404, "Departure not found.")
    with db.connect() as connection:
        if change.saved:
            connection.execute(
                "INSERT OR IGNORE INTO group_requests(owner,departure) VALUES (?,?)",
                (request.state.owner, group_id),
            )
        else:
            connection.execute(
                "DELETE FROM group_requests WHERE owner=? AND departure=?",
                (request.state.owner, group_id),
            )
    return {"status": "pending" if change.saved else None, "demo": True}
