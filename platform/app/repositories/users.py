"""SQL access for auth.users."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


SELECT_COLS = """
    user_id, email, full_name, password_hash, provider, google_sub,
    picture, created_at, last_login_at
"""


async def get_by_email(session: AsyncSession, email: str) -> Optional[dict]:
    row = (await session.execute(
        text(f"SELECT {SELECT_COLS} FROM auth.users WHERE LOWER(email) = LOWER(:e)"),
        {"e": email},
    )).first()
    return dict(row._mapping) if row else None


async def get_by_id(session: AsyncSession, user_id: int) -> Optional[dict]:
    row = (await session.execute(
        text(f"SELECT {SELECT_COLS} FROM auth.users WHERE user_id = :id"),
        {"id": user_id},
    )).first()
    return dict(row._mapping) if row else None


async def get_by_google_sub(session: AsyncSession, sub: str) -> Optional[dict]:
    row = (await session.execute(
        text(f"SELECT {SELECT_COLS} FROM auth.users WHERE google_sub = :s"),
        {"s": sub},
    )).first()
    return dict(row._mapping) if row else None


async def create_local(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    full_name: str,
) -> dict:
    row = (await session.execute(
        text(f"""
            INSERT INTO auth.users (email, password_hash, full_name, provider)
            VALUES (:email, :ph, :name, 'local')
            RETURNING {SELECT_COLS}
        """),
        {"email": email, "ph": password_hash, "name": full_name},
    )).one()
    await session.commit()
    return dict(row._mapping)


async def create_google(
    session: AsyncSession,
    *,
    email: str,
    full_name: str,
    google_sub: str,
    picture: Optional[str],
) -> dict:
    row = (await session.execute(
        text(f"""
            INSERT INTO auth.users
                (email, full_name, provider, google_sub, picture)
            VALUES (:email, :name, 'google', :sub, :pic)
            RETURNING {SELECT_COLS}
        """),
        {"email": email, "name": full_name, "sub": google_sub, "pic": picture},
    )).one()
    await session.commit()
    return dict(row._mapping)


async def touch_last_login(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        text("UPDATE auth.users SET last_login_at = now() WHERE user_id = :id"),
        {"id": user_id},
    )
    await session.commit()


async def update_picture_if_changed(
    session: AsyncSession, user_id: int, picture: Optional[str]
) -> None:
    if picture is None:
        return
    await session.execute(
        text("""
            UPDATE auth.users SET picture = :p
            WHERE user_id = :id AND (picture IS DISTINCT FROM :p)
        """),
        {"id": user_id, "p": picture},
    )
    await session.commit()
