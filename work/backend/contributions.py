"""Account-owned, unverified observations, kept separate from illustrative catalog scores."""

import re
import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import db
from .catalog import BY_ID, PLACES, slh_score

router = APIRouter(prefix="/api")
COMMUNITY_THRESHOLD = 3
REPORT_THRESHOLD = 3


class ContributionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    safety: int | None = Field(default=None, ge=1, le=5, strict=True)
    legitimacy: int | None = Field(default=None, ge=1, le=5, strict=True)
    hygiene: int | None = Field(default=None, ge=1, le=5, strict=True)
    tip: str = Field(default="", max_length=500)
    tip_category: (
        Literal["best time", "cost", "accessibility", "food", "safety", "hygiene", "general"] | None
    ) = None
    visit_date: date
    personal_experience: Literal[True]

    @field_validator("visit_date", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Choose a calendar visit date (YYYY-MM-DD).")
        return value

    @field_validator("visit_date")
    @classmethod
    def past_visit(cls, value):
        if value > date.today():
            raise ValueError("Your visit date cannot be in the future.")
        return value

    @field_validator("tip")
    @classmethod
    def reject_spam(cls, value):
        if len(re.findall(r"https?://|www\.", value, re.I)) > 1 or re.search(r"(.)\1{14,}", value):
            raise ValueError("Remove repeated text and excessive links from your tip.")
        return value

    @model_validator(mode="after")
    def complete_contribution(self):
        ratings = [self.safety, self.legitimacy, self.hygiene]
        if any(v is not None for v in ratings) and any(v is None for v in ratings):
            raise ValueError("Rate all three SLH dimensions, or submit a tip only.")
        if self.safety is None and not self.tip:
            raise ValueError("Add an SLH rating or a local tip.")
        if not self.tip:
            self.tip_category = None
        return self


def account(request):
    user = request.state.user
    if not user:
        raise HTTPException(401, "Sign in to contribute.")
    if not user["role_selected"]:
        raise HTTPException(403, "Choose your tourist or local role before contributing.")
    return user["id"]


def known_place(place_id):
    if place_id not in BY_ID:
        raise HTTPException(404, "Choose a location from the catalog.")


def current_places(connection):
    rows = connection.execute(
        "SELECT place, COUNT(*) AS reviews, AVG(safety) AS safety, "
        "AVG(legitimacy) AS legitimacy, AVG(hygiene) AS hygiene, MAX(updated_at) AS reviewed_at "
        "FROM place_contributions WHERE safety IS NOT NULL AND rating_status='published' GROUP BY place"
    ).fetchall()
    aggregates = {row["place"]: {**dict(row), "source": "community"} for row in rows}
    result = []
    for place in PLACES:
        demo = {**place["slh"], "source": "demo"}
        community = aggregates.get(place["id"])
        eligible = community is not None and community["reviews"] >= COMMUNITY_THRESHOLD
        source = "community" if eligible else "demo" if slh_score(demo) is not None else "unrated"
        result.append(
            {
                **place,
                "demo_slh": demo,
                "community_slh": community,
                "slh": community if eligible else {**demo, "source": source},
                "slh_source": source,
                "community_threshold": COMMUNITY_THRESHOLD,
            }
        )
    return result


def own_contribution(connection, place_id, owner):
    row = connection.execute(
        "SELECT id, place, safety, legitimacy, hygiene, tip, tip_category, visit_date, "
        "rating_status, tip_status, created_at, updated_at FROM place_contributions WHERE place=? AND owner=?",
        (place_id, owner),
    ).fetchone()
    return dict(row) if row else None


@router.get("/places/{place_id}/contribution")
def get_own(place_id: str, request: Request):
    owner = account(request)
    known_place(place_id)
    with db.connect() as connection:
        visited = connection.execute(
            "SELECT 1 FROM visited_places WHERE owner=? AND place=?", (owner, place_id)
        ).fetchone()
        return {
            "contribution": own_contribution(connection, place_id, owner),
            "self_reported_visit": bool(visited),
        }


@router.put("/places/{place_id}/contribution")
def save(place_id: str, contribution: ContributionInput, request: Request):
    owner = account(request)
    known_place(place_id)
    with db.connect() as connection:
        # UPSERT retains moderation state and reports, including across edits to reported text.
        connection.execute(
            "INSERT INTO place_contributions(id,owner,place,safety,legitimacy,hygiene,tip,tip_category,visit_date) "
            "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(owner,place) DO UPDATE SET "
            "safety=excluded.safety,legitimacy=excluded.legitimacy,hygiene=excluded.hygiene,"
            "tip=excluded.tip,tip_category=excluded.tip_category,visit_date=excluded.visit_date,"
            "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
            (
                secrets.token_urlsafe(12),
                owner,
                place_id,
                contribution.safety,
                contribution.legitimacy,
                contribution.hygiene,
                contribution.tip,
                contribution.tip_category,
                str(contribution.visit_date),
            ),
        )
        return own_contribution(connection, place_id, owner)


@router.delete("/places/{place_id}/contribution")
def delete(place_id: str, request: Request):
    owner = account(request)
    known_place(place_id)
    with db.connect() as connection:
        connection.execute(
            "DELETE FROM place_contributions WHERE owner=? AND place=?", (owner, place_id)
        )
    return {"deleted": True}


@router.get("/places/{place_id}/tips")
def tips(place_id: str, request: Request, offset: int = Query(default=0, ge=0)):
    known_place(place_id)
    user = request.state.user
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT id,tip,tip_category,visit_date,updated_at,owner=? AS is_owner "
            "FROM place_contributions WHERE place=? AND tip!='' AND tip_status='published' "
            "ORDER BY updated_at DESC,id LIMIT 21 OFFSET ?",
            (user["id"] if user else "", place_id, offset),
        ).fetchall()
        return {
            "tips": [{**dict(r), "is_owner": bool(r["is_owner"])} for r in rows[:20]],
            "next_offset": offset + 20 if len(rows) > 20 else None,
        }


@router.post("/tips/{contribution_id}/reports")
def report(contribution_id: str, request: Request):
    owner = account(request)
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT owner,tip FROM place_contributions WHERE id=?", (contribution_id,)
        ).fetchone()
        if not row or not row["tip"]:
            raise HTTPException(404, "Tip not found.")
        if row["owner"] == owner:
            raise HTTPException(422, "Edit or delete your own tip instead.")
        connection.execute(
            "INSERT OR IGNORE INTO tip_reports(contribution,reporter) VALUES (?,?)",
            (contribution_id, owner),
        )
        count = connection.execute(
            "SELECT COUNT(*) FROM tip_reports WHERE contribution=?", (contribution_id,)
        ).fetchone()[0]
        status = "hidden" if count >= REPORT_THRESHOLD else "reported"
        connection.execute(
            "UPDATE place_contributions SET tip_status=? WHERE id=?", (status, contribution_id)
        )
        return {"reported": True}
