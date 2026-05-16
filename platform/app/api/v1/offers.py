from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories import offers as offers_repo
from app.schemas.offer import OfferListResponse, OfferOut

router = APIRouter(prefix="/offers", tags=["Offers"])


@router.get("", response_model=OfferListResponse)
async def list_offers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    pays: Optional[str] = None,
    metier_code: Optional[str] = None,
    q: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    total, items = await offers_repo.list_offers(
        session, limit=limit, offset=offset, pays=pays, metier_code=metier_code, q=q
    )
    return OfferListResponse(total=total, items=items)


@router.get("/{offer_id}", response_model=OfferOut)
async def get_offer(offer_id: int, session: AsyncSession = Depends(get_session)):
    offer = await offers_repo.get_offer(session, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer
