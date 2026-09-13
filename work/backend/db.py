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
        CREATE TABLE IF NOT EXISTS trips (id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES sessions(id), plan TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS trips_owner ON trips(owner);
        CREATE TABLE IF NOT EXISTS completions (trip TEXT NOT NULL REFERENCES trips(id), stop TEXT NOT NULL, PRIMARY KEY(trip,stop));
        CREATE TABLE IF NOT EXISTS bookmarks (owner TEXT NOT NULL REFERENCES sessions(id), template TEXT NOT NULL, PRIMARY KEY(owner,template));
        CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES sessions(id), content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS group_requests (owner TEXT NOT NULL REFERENCES sessions(id), departure TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', PRIMARY KEY(owner,departure));
        """)
