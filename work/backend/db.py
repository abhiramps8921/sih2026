import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("ROAM_DB_PATH", Path(__file__).with_name("roam.db")))


@contextmanager
def connect():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY REFERENCES sessions(id), email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT CHECK(role IN ('tourist','local')));
        CREATE TABLE IF NOT EXISTS account_sessions (token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id), expires_at INTEGER NOT NULL, role_selected INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS auth_attempts (key TEXT PRIMARY KEY, attempts INTEGER NOT NULL, reset_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS trips (id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES sessions(id), plan TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS trips_owner ON trips(owner);
        CREATE TABLE IF NOT EXISTS completions (trip TEXT NOT NULL REFERENCES trips(id), stop TEXT NOT NULL, PRIMARY KEY(trip,stop));
        CREATE TABLE IF NOT EXISTS visited_places (
            owner TEXT NOT NULL REFERENCES sessions(id),
            place TEXT NOT NULL,
            visited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(owner, place)
        );
        CREATE INDEX IF NOT EXISTS visited_places_owner ON visited_places(owner);
        CREATE TABLE IF NOT EXISTS bookmarks (owner TEXT NOT NULL REFERENCES sessions(id), template TEXT NOT NULL, PRIMARY KEY(owner,template));
        CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES sessions(id), content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS group_requests (owner TEXT NOT NULL REFERENCES sessions(id), departure TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', PRIMARY KEY(owner,departure));
        CREATE TABLE IF NOT EXISTS travel_groups (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES accounts(id),
            name TEXT NOT NULL, date TEXT NOT NULL, meeting_point TEXT NOT NULL,
            capacity INTEGER NOT NULL CHECK(capacity BETWEEN 2 AND 50), interests TEXT NOT NULL,
            shared_itinerary TEXT, closed INTEGER NOT NULL DEFAULT 0 CHECK(closed IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS group_memberships (
            group_id TEXT NOT NULL REFERENCES travel_groups(id),
            account_id TEXT NOT NULL REFERENCES accounts(id),
            PRIMARY KEY(group_id, account_id)
        );
        CREATE INDEX IF NOT EXISTS memberships_account ON group_memberships(account_id);
        CREATE TABLE IF NOT EXISTS place_contributions (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES accounts(id),
            place TEXT NOT NULL, safety INTEGER, legitimacy INTEGER, hygiene INTEGER,
            tip TEXT NOT NULL DEFAULT '', tip_category TEXT,
            visit_date TEXT NOT NULL,
            rating_status TEXT NOT NULL DEFAULT 'published' CHECK(rating_status IN ('published','hidden')),
            tip_status TEXT NOT NULL DEFAULT 'published' CHECK(tip_status IN ('published','reported','hidden')),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(owner, place),
            CHECK((safety IS NULL AND legitimacy IS NULL AND hygiene IS NULL) OR
                  (safety IS NOT NULL AND legitimacy IS NOT NULL AND hygiene IS NOT NULL AND
                   safety BETWEEN 1 AND 5 AND legitimacy BETWEEN 1 AND 5 AND hygiene BETWEEN 1 AND 5)),
            CHECK(safety IS NOT NULL OR length(trim(tip)) > 0)
        );
        CREATE INDEX IF NOT EXISTS contributions_place ON place_contributions(place);
        CREATE TABLE IF NOT EXISTS tip_reports (
            contribution TEXT NOT NULL REFERENCES place_contributions(id) ON DELETE CASCADE,
            reporter TEXT NOT NULL REFERENCES accounts(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(contribution, reporter)
        );
        """)
        completed_stops = db.execute(
            "SELECT t.owner, t.plan, c.stop FROM completions c JOIN trips t ON t.id=c.trip"
        ).fetchall()
        for row in completed_stops:
            plan = json.loads(row["plan"])
            place_id = next(
                (
                    stop["place"]["id"]
                    for day in plan["days"]
                    for stop in day["stops"]
                    if stop["id"] == row["stop"]
                ),
                None,
            )
            if place_id is not None:
                db.execute(
                    "INSERT OR IGNORE INTO visited_places(owner,place) VALUES (?,?)",
                    (row["owner"], place_id),
                )
