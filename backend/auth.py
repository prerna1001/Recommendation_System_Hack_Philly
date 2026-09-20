"""Company auth: one shared login per company (not per individual member).

Session tokens live in the `sessions` table and are handed to the browser as
an httpOnly cookie -- chosen over a signed JWT so logout (delete the row) is
a real revocation, not just "the browser forgot the token."
"""
import secrets

import bcrypt
from fastapi import HTTPException, Request, Response

from db import get_db

SESSION_COOKIE = "session_token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session(conn, company_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token, company_id) VALUES (%s, %s)", (token, company_id)
    )
    conn.commit()
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax", secure=False, max_age=60 * 60 * 24 * 30
    )


def get_current_company(request: Request) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not logged in")
    conn = get_db()
    row = conn.execute(
        "SELECT company_id FROM sessions WHERE token = %s", (token,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "Session expired or invalid")
    return row["company_id"]
