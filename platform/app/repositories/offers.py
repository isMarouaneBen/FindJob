"""
SQL access layer for offers — reads from v_offer_recommandation (already
excludes duplicates) for the list/detail endpoints.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.offer import OfferOut


_OFFER_COLS = """
    offer_id, poste, NULL AS titre_original,
    societe_nom, ville_nom, pays_nom,
    metier_libelle, contrat_libelle, seniorite_libelle,
    teletravail_libelle, niveau_diplome,
    experience_min_annees, experience_max_annees,
    salaire_min, salaire_max, devise,
    salaire_min_mensuel_eur, salaire_max_mensuel_eur,
    competences, langues, date_publication, url, quality_score
"""


def _row_to_offer(row) -> OfferOut:
    m = row._mapping
    return OfferOut(
        offer_id=m["offer_id"],
        poste=m["poste"],
        titre_original=m.get("titre_original"),
        societe_nom=m.get("societe_nom"),
        ville_nom=m.get("ville_nom"),
        pays_nom=m.get("pays_nom"),
        metier_libelle=m.get("metier_libelle"),
        contrat_libelle=m.get("contrat_libelle"),
        seniorite_libelle=m.get("seniorite_libelle"),
        teletravail_libelle=m.get("teletravail_libelle"),
        niveau_diplome=m.get("niveau_diplome"),
        experience_min_annees=m.get("experience_min_annees") or 0,
        experience_max_annees=m.get("experience_max_annees") or 0,
        salaire_min=m.get("salaire_min"),
        salaire_max=m.get("salaire_max"),
        devise=m.get("devise"),
        salaire_min_mensuel_eur=m.get("salaire_min_mensuel_eur") or 0,
        salaire_max_mensuel_eur=m.get("salaire_max_mensuel_eur") or 0,
        competences=list(m.get("competences") or []),
        langues=list(m.get("langues") or []),
        date_publication=m.get("date_publication"),
        url=m.get("url"),
        quality_score=m.get("quality_score") or 0,
    )


async def list_offers(
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    pays: Optional[str] = None,
    metier_code: Optional[str] = None,
    q: Optional[str] = None,
) -> Tuple[int, List[OfferOut]]:
    conditions = []
    params: dict = {"limit": limit, "offset": offset}
    if pays:
        conditions.append("pays_nom = :pays")
        params["pays"] = pays
    if metier_code:
        conditions.append("metier_code = :metier")
        params["metier"] = metier_code
    if q:
        conditions.append("poste ILIKE :q")
        params["q"] = f"%{q}%"

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_sql = f"SELECT COUNT(*) FROM analytics.v_offer_recommandation {where}"
    total = (await session.execute(sql_text(count_sql), params)).scalar_one()

    list_sql = f"""
        SELECT {_OFFER_COLS}
        FROM analytics.v_offer_recommandation
        {where}
        ORDER BY date_publication DESC NULLS LAST, offer_id DESC
        LIMIT :limit OFFSET :offset
    """
    rows = (await session.execute(sql_text(list_sql), params)).all()
    return total, [_row_to_offer(r) for r in rows]


async def get_offer(session: AsyncSession, offer_id: int) -> Optional[OfferOut]:
    sql = f"""
        SELECT {_OFFER_COLS}
        FROM analytics.v_offer_recommandation
        WHERE offer_id = :id
    """
    row = (await session.execute(sql_text(sql), {"id": offer_id})).first()
    return _row_to_offer(row) if row else None
