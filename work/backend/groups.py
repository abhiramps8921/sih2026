import json
import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import db

router = APIRouter(prefix="/api/groups")


class GroupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=3, max_length=100)
    date: date
    meeting_point: str = Field(min_length=3, max_length=200)
    capacity: int = Field(ge=2, le=50, strict=True)
    interests: list[Literal["Food", "Culture", "Nature", "Art", "Hidden gems", "Shopping"]] = Field(
        min_length=1, max_length=6
    )
    itinerary_id: str | None = Field(default=None, min_length=1, max_length=100)
    share_itinerary: bool = False

    @field_validator("date")
    @classmethod
    def future_date(cls, value):
        if value < date.today() or value.year > 2100:
            raise ValueError("Choose a date from today through 2100.")
        return value

    @model_validator(mode="after")
    def explicit_sharing(self):
        if bool(self.itinerary_id) != self.share_itinerary:
            raise ValueError("Confirm sharing the itinerary title and stop names to link it.")
        return self


def account(request):
    if not request.state.user:
        raise HTTPException(401, "Sign in to use groups.")
    return request.state.user["id"]


def load_group(connection, group_id, user):
    row = connection.execute(
        "SELECT g.*, (SELECT COUNT(*) FROM group_memberships WHERE group_id=g.id) AS members, "
        "EXISTS(SELECT 1 FROM group_memberships WHERE group_id=g.id AND account_id=?) AS joined "
        "FROM travel_groups g WHERE g.id=?",
        (user, group_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Group not found.")
    return {
        "id": row["id"],
        "name": row["name"],
        "date": row["date"],
        "meeting_point": row["meeting_point"],
        "capacity": row["capacity"],
        "interests": json.loads(row["interests"]),
        "members": row["members"],
        "remaining": row["capacity"] - row["members"],
        "joined": bool(row["joined"]),
        "is_owner": row["owner"] == user,
        "closed": bool(row["closed"]),
        "shared_itinerary": json.loads(row["shared_itinerary"])
        if row["shared_itinerary"]
        else None,
    }


@router.get("")
def list_groups(request: Request, offset: int = Query(default=0, ge=0)):
    user = account(request)
    with db.connect() as connection:
        ids = connection.execute(
            "SELECT g.id FROM travel_groups g WHERE "
            "(g.closed=0 AND g.date>=?) OR g.owner=? OR EXISTS "
            "(SELECT 1 FROM group_memberships m WHERE m.group_id=g.id AND m.account_id=?) "
            "ORDER BY g.date, g.created_at, g.id LIMIT 21 OFFSET ?",
            (str(date.today()), user, user, offset),
        ).fetchall()
        return {
            "groups": [load_group(connection, row["id"], user) for row in ids[:20]],
            "next_offset": offset + 20 if len(ids) > 20 else None,
        }


@router.post("", status_code=201)
def create_group(data: GroupInput, request: Request):
    user = account(request)
    group_id = secrets.token_urlsafe(16)
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        shared = None
        if data.itinerary_id:
            row = connection.execute(
                "SELECT plan FROM trips WHERE id=? AND owner=?", (data.itinerary_id, user)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Choose an itinerary from your own trips.")
            plan = json.loads(row["plan"])
            # Snapshot only the fields the creator explicitly agreed to publish.
            shared = json.dumps(
                {
                    "title": plan["title"],
                    "days": [
                        {"stops": [stop["place"]["name"] for stop in day["stops"]]}
                        for day in plan["days"]
                    ],
                }
            )
        connection.execute(
            "INSERT INTO travel_groups(id,owner,name,date,meeting_point,capacity,interests,shared_itinerary) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                group_id,
                user,
                data.name,
                str(data.date),
                data.meeting_point,
                data.capacity,
                json.dumps(list(dict.fromkeys(data.interests))),
                shared,
            ),
        )
        connection.execute("INSERT INTO group_memberships VALUES (?,?)", (group_id, user))
        return load_group(connection, group_id, user)


@router.put("/{group_id}/membership")
def join_group(group_id: str, request: Request):
    user = account(request)
    with db.connect() as connection:
        # Serialize the capacity check and membership write across SQLite connections.
        connection.execute("BEGIN IMMEDIATE")
        group = load_group(connection, group_id, user)
        if group["joined"]:
            return group
        if group["closed"] or group["date"] < str(date.today()):
            raise HTTPException(409, "This group is closed or its date has passed.")
        if not group["remaining"]:
            raise HTTPException(409, "This group is full.")
        connection.execute("INSERT INTO group_memberships VALUES (?,?)", (group_id, user))
        return load_group(connection, group_id, user)


@router.delete("/{group_id}/membership")
def leave_group(group_id: str, request: Request):
    user = account(request)
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        group = load_group(connection, group_id, user)
        if group["is_owner"] and not group["closed"]:
            raise HTTPException(409, "Close your group before leaving.")
        connection.execute(
            "DELETE FROM group_memberships WHERE group_id=? AND account_id=?", (group_id, user)
        )
        return load_group(connection, group_id, user)


@router.post("/{group_id}/close")
def close_group(group_id: str, request: Request):
    user = account(request)
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        group = load_group(connection, group_id, user)
        if not group["is_owner"]:
            raise HTTPException(403, "Only the owner can close this group.")
        connection.execute("UPDATE travel_groups SET closed=1 WHERE id=?", (group_id,))
        return load_group(connection, group_id, user)
