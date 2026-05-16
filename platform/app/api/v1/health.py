from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.kafka_producer import _enabled as kafka_enabled  # noqa: PLC2701
from app.services.redis_client import get_redis

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"db unavailable: {e}")
    return {
        "status": "ok",
        "db": "connected",
        "redis": "connected" if get_redis() else "disabled",
        "kafka": "connected" if kafka_enabled else "disabled",
    }
