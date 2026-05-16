from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.offer import OfferOut
from app.schemas.profile import ProfileForm


class RecommendationRequest(BaseModel):
    profile: ProfileForm
    top_k: int = Field(20, ge=1, le=100)
    only_pays: Optional[List[str]] = None  # e.g. ["Maroc", "France"]
    min_salary_eur: Optional[int] = Field(None, ge=0)
    only_remote: bool = False  # if True, exclude offers with teletravail_libelle == 'Non'


class ScoreBreakdown(BaseModel):
    vector: float
    tech_overlap: float
    seniority: float
    contract: float
    location: float
    remote: float
    language: float


class RecommendedOffer(BaseModel):
    offer: OfferOut
    score: float
    breakdown: ScoreBreakdown
    matched_technologies: List[str] = []
    missing_technologies: List[str] = []


class RecommendationResponse(BaseModel):
    count: int
    items: List[RecommendedOffer]
