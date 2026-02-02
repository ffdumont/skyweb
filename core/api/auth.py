"""Firebase Auth JWT verification middleware."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Header, HTTPException

if TYPE_CHECKING:
    pass


@dataclass
class UserClaims:
    uid: str
    email: str | None = None
    name: str | None = None


async def verify_firebase_token(
    authorization: str | None = Header(None, description="Bearer <Firebase ID token>"),
) -> UserClaims:
    """Extract and verify a Firebase Auth ID token from the Authorization header.

    In development, set ``SKYWEB_AUTH_DISABLED=1`` to bypass verification
    and use a fixed test user.
    """
    if os.environ.get("SKYWEB_AUTH_DISABLED") == "1":
        return UserClaims(uid="dev-user", email="dev@localhost", name="Dev User")

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    try:
        from firebase_admin import auth as firebase_auth

        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    return UserClaims(
        uid=decoded["uid"],
        email=decoded.get("email"),
        name=decoded.get("name"),
    )
