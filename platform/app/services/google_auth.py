"""
Server-side verification of Google ID tokens.

`google-auth` checks:
  • signature against Google's published JWKs (cached)
  • issuer (`accounts.google.com` or `https://accounts.google.com`)
  • audience equals our GOOGLE_CLIENT_ID
  • expiration

Returns the relevant fields. Raises ValueError on invalid token.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, TypedDict

from google.auth.transport import requests as ga_requests
from google.oauth2 import id_token

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleIdentity(TypedDict):
    sub: str
    email: str
    email_verified: bool
    name: str
    picture: Optional[str]


def _verify_sync(credential: str) -> GoogleIdentity:
    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError(
            "Server is not configured for Google OAuth (GOOGLE_CLIENT_ID is empty)."
        )
    info = id_token.verify_oauth2_token(
        credential,
        ga_requests.Request(),
        audience=settings.GOOGLE_CLIENT_ID,
        # Tolerate small clock drift between Google and the container's clock
        # (Docker Desktop / WSL2 occasionally lag a second or two), which
        # otherwise raises "Token used too early".
        clock_skew_in_seconds=10,
    )
    if not info.get("email_verified"):
        raise ValueError("Google account email is not verified.")
    return GoogleIdentity(
        sub=info["sub"],
        email=info["email"].lower(),
        email_verified=bool(info["email_verified"]),
        name=info.get("name") or info["email"],
        picture=info.get("picture"),
    )


async def verify_credential(credential: str) -> GoogleIdentity:
    return await asyncio.to_thread(_verify_sync, credential)
