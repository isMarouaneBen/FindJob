from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class OfferOut(BaseModel):
    offer_id: int
    poste: str
    titre_original: Optional[str] = None
    societe_nom: Optional[str] = None
    ville_nom: Optional[str] = None
    pays_nom: Optional[str] = None
    metier_libelle: Optional[str] = None
    contrat_libelle: Optional[str] = None
    seniorite_libelle: Optional[str] = None
    teletravail_libelle: Optional[str] = None
    niveau_diplome: Optional[str] = None
    experience_min_annees: int = 0
    experience_max_annees: int = 0
    salaire_min: Optional[Decimal] = None
    salaire_max: Optional[Decimal] = None
    devise: Optional[str] = None
    salaire_min_mensuel_eur: int = 0
    salaire_max_mensuel_eur: int = 0
    competences: List[str] = Field(default_factory=list)
    langues: List[str] = Field(default_factory=list)
    date_publication: Optional[date] = None
    url: Optional[str] = None
    quality_score: int = 0


class OfferListResponse(BaseModel):
    total: int
    items: List[OfferOut]
