import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from . import db

router = APIRouter(prefix="/api/auth")
SESSION_AGE = 60 * 60 * 24 * 30


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class RoleChoice(BaseModel):
    role: Literal["tourist", "local"]


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()


def token_hash(request):
    return hashlib.sha256(request.cookies.get("roam_auth", "").encode()).hexdigest()


def resolve_user(request):
    with db.connect() as connection:
        row = connection.execute(
            "SELECT a.id, a.email, a.role, s.role_selected FROM account_sessions s "
            "JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=? AND s.expires_at>?",
            (token_hash(request), int(time.time())),
        ).fetchone()
    return {**dict(row), "role_selected": bool(row["role_selected"])} if row else None


def start_session(connection, account_id, request, response):
    token = secrets.token_urlsafe(32)
    connection.execute(
        "DELETE FROM auth_attempts WHERE key = 'email:' || (SELECT email FROM accounts WHERE id=?)",
        (account_id,),
    )
    connection.execute(
        "DELETE FROM account_sessions WHERE token_hash=? OR expires_at<=?",
        (token_hash(request), int(time.time())),
    )
    connection.execute(
        "INSERT INTO account_sessions(token_hash,account_id,expires_at) VALUES (?,?,?)",
        (hashlib.sha256(token.encode()).hexdigest(), account_id, int(time.time()) + SESSION_AGE),
    )
    response.set_cookie(
        "roam_auth",
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=SESSION_AGE,
    )


def limit_attempts(email, request):
    now = int(time.time())
    keys = [
        ("email:" + email, 10),
        ("ip:" + (request.client.host if request.client else "unknown"), 60),
    ]
    with db.connect() as connection:
        connection.execute("DELETE FROM auth_attempts WHERE reset_at<=?", (now,))
        for key, limit in keys:
            row = connection.execute(
                "SELECT attempts FROM auth_attempts WHERE key=?", (key,)
            ).fetchone()
            if row and row["attempts"] >= limit:
                raise HTTPException(429, "Too many attempts. Please try again in 15 minutes.")
        for key, _ in keys:
            connection.execute(
                "INSERT INTO auth_attempts(key,attempts,reset_at) VALUES (?,1,?) "
                "ON CONFLICT(key) DO UPDATE SET attempts=attempts+1",
                (key, now + 900),
            )


@router.post("/signup", status_code=201)
def signup(data: Credentials, request: Request, response: Response):
    limit_attempts(data.email, request)
    salt = secrets.token_bytes(16)
    stored = salt.hex() + ":" + password_hash(data.password, salt)
    account_id = secrets.token_urlsafe(32)
    try:
        with db.connect() as connection:
            connection.execute("INSERT INTO sessions(id) VALUES (?)", (account_id,))
            connection.execute(
                "INSERT INTO accounts(id,email,password_hash) VALUES (?,?,?)",
                (account_id, data.email, stored),
            )
            start_session(connection, account_id, request, response)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            409, "An account with this email already exists. Please log in."
        ) from exc
    return {"email": data.email}


@router.post("/login")
def login(data: Credentials, request: Request, response: Response):
    limit_attempts(data.email, request)
    with db.connect() as connection:
        account = connection.execute(
            "SELECT * FROM accounts WHERE email=?", (data.email,)
        ).fetchone()
        salt, expected = account["password_hash"].split(":") if account else ("00" * 16, "00" * 64)
        actual = password_hash(data.password, bytes.fromhex(salt))
        if not hmac.compare_digest(actual, expected) or not account:
            raise HTTPException(401, "Email or password is incorrect.")
        start_session(connection, account["id"], request, response)
    return {"email": data.email}


@router.put("/role")
def choose_role(data: RoleChoice, request: Request):
    if not request.state.user:
        raise HTTPException(401, "Please log in first.")
    with db.connect() as connection:
        connection.execute(
            "UPDATE accounts SET role=? WHERE id=?", (data.role, request.state.user["id"])
        )
        connection.execute(
            "UPDATE account_sessions SET role_selected=1 WHERE token_hash=?", (token_hash(request),)
        )
    return {"role": data.role}


@router.post("/logout")
def logout(request: Request, response: Response):
    with db.connect() as connection:
        connection.execute(
            "DELETE FROM account_sessions WHERE token_hash=?", (token_hash(request),)
        )
    response.delete_cookie("roam_auth", httponly=True, samesite="strict")
    return {"ok": True}
