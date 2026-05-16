"""
Hybrid recommendation engine.

Two-stage retrieval:

  Stage 1 — ANN candidate retrieval (Postgres pgvector)
      • Embed the profile with the same model used for offers.
      • Use the `<=>` cosine-distance operator on `analytics.fact_offer.embedding`.
      • Apply hard SQL filters (only non-duplicates, salary floor, country,
        remote-only) so the candidate pool is already relevant.
      • Pull RECO_VECTOR_CANDIDATES rows ordered by distance.

  Stage 2 — Python re-rank with weighted signals
      • vector similarity (1 - cosine distance)
      • technology overlap (Jaccard on canonical names)
      • seniority match (ordinal distance, decayed)
      • contract match (1.0 if user list contains offer.contrat)
      • location match (city in user list → 1.0, country → 0.5)
      • remote preference match
      • language overlap

  Final score = Σ wᵢ · signalᵢ where weights are configurable via settings.

Scores are in [0, 1], deterministic given the same inputs.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.offer import OfferOut
from app.schemas.profile import ProfilePayload, SeniorityLevel
from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendedOffer,
    ScoreBreakdown,
)
from app.services import tech_extractor
from app.services.embedding import embed_one

logger = logging.getLogger(__name__)

# Ordinal ordering for seniority — matches dim_seniorite.ordre.
# Keyed on lowercased + accent-stripped form so both the profile enum codes
# (Confirme, Intermediaire, Expert) and the DB libellés with accents
# (Confirmé, Intermédiaire, "Expert / Lead") resolve to the same bucket.
SENIORITY_ORDER: Dict[str, int] = {
    "stage": 10, "alternance": 20, "junior": 30, "intermediaire": 40,
    "confirme": 50, "senior": 60, "expert": 70,
}


def _seniority_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    import unicodedata
    # Strip accents, lowercase, take the first significant token so that
    # "Expert / Lead" → "expert", "Intermédiaire" → "intermediaire".
    norm = unicodedata.normalize("NFD", value)
    ascii_ = "".join(c for c in norm if unicodedata.category(c) != "Mn").lower()
    token = ascii_.split("/")[0].split()[0].strip() if ascii_ else ""
    return token or None


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _normalize_set(values) -> Set[str]:
    if not values:
        return set()
    return {_norm(v) for v in values if v}


def _tech_overlap(user: Set[str], offer: Set[str]) -> Tuple[float, List[str], List[str]]:
    if not user or not offer:
        return 0.0, [], []
    inter = user & offer
    union = user | offer
    matched = sorted(inter)
    missing = sorted(offer - user)
    return len(inter) / len(union), matched, missing


def _seniority_score(profile: Optional[SeniorityLevel], offer_lib: Optional[str]) -> Optional[float]:
    """Return None when the signal is not informative (so its weight is
    redistributed to other signals instead of padding the score with 0.5)."""
    if not profile or not offer_lib:
        return None
    p_ord = SENIORITY_ORDER.get(_seniority_key(profile.value))
    o_ord = SENIORITY_ORDER.get(_seniority_key(offer_lib))
    if p_ord is None or o_ord is None:
        return None
    diff = abs(p_ord - o_ord)
    return max(0.0, 1.0 - diff / 70.0)


def _contract_score(user_contracts, offer_contrat: Optional[str]) -> Optional[float]:
    if not user_contracts or not offer_contrat or offer_contrat == "Non spécifié":
        return None
    user = {c.value if hasattr(c, "value") else c for c in user_contracts}
    return 1.0 if offer_contrat in user else 0.0


def _location_score(profile: ProfilePayload, offer: OfferOut) -> Optional[float]:
    if not profile.villes and not profile.pays:
        return None
    villes = {_norm(v) for v in profile.villes}
    pays = {_norm(p) for p in profile.pays}
    if _norm(offer.ville_nom) in villes:
        return 1.0
    if _norm(offer.pays_nom) in pays:
        return 0.6
    return 0.0


def _remote_score(profile: ProfilePayload, offer: OfferOut) -> Optional[float]:
    if profile.remote is None or not offer.teletravail_libelle:
        return None
    lib = _norm(offer.teletravail_libelle)
    if lib in {"non spécifié", ""}:
        return None
    pref = _norm(profile.remote.value)
    if pref == "total" and "remote" in lib:
        return 1.0
    if pref == "hybride" and "hybride" in lib:
        return 1.0
    if pref == "possible" and lib in {"possible / occasionnel", "hybride", "100% remote"}:
        return 0.8
    if pref == "non" and lib == "non":
        return 1.0
    return 0.2


def _language_score(user_langs: Set[str], offer_langs: Set[str]) -> Optional[float]:
    if not offer_langs or not user_langs:
        return None
    inter = user_langs & offer_langs
    return len(inter) / len(offer_langs)


def _quality_score(quality: int) -> float:
    """Quality bump in [0, 1] derived from offers' quality_score [0, 100]."""
    return max(0.0, min(1.0, quality / 100.0))


def _freshness_score(date_pub) -> Optional[float]:
    """1.0 for offers ≤ 7 days old, decaying to 0 over 90 days."""
    if not date_pub:
        return None
    from datetime import date as _date
    if isinstance(date_pub, str):
        try:
            date_pub = _date.fromisoformat(date_pub)
        except ValueError:
            return None
    days = (_date.today() - date_pub).days
    if days <= 7:
        return 1.0
    if days >= 90:
        return 0.0
    return max(0.0, 1.0 - (days - 7) / 83.0)


async def _retrieve_candidates(
    session: AsyncSession,
    profile_embedding: List[float],
    request: RecommendationRequest,
) -> List[dict]:
    """Stage 1: vector ANN retrieval with hard SQL filters."""
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in profile_embedding) + "]"

    conditions = ["f.embedding IS NOT NULL", "NOT f.is_duplicate"]
    params: Dict[str, object] = {
        "vec": vec_literal,
        "limit": settings.RECO_VECTOR_CANDIDATES,
    }

    if request.only_pays:
        conditions.append("p.pays_nom = ANY(:pays)")
        params["pays"] = request.only_pays

    if request.min_salary_eur:
        conditions.append("f.salaire_max_mensuel_eur >= :min_sal")
        params["min_sal"] = request.min_salary_eur

    if request.only_remote:
        conditions.append("t.teletravail_libelle <> 'Non'")

    # If the profile specifies a metier_code, restrict to that family.
    metier_code = (request.profile.metier_code or "").strip().upper()
    if metier_code:
        conditions.append("m.metier_code = :metier_code")
        params["metier_code"] = metier_code

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            f.offer_id,
            f.poste,
            f.titre_original,
            soc.societe_nom,
            v.ville_nom,
            p.pays_nom,
            m.metier_libelle,
            c.contrat_libelle,
            sen.seniorite_libelle,
            t.teletravail_libelle,
            nd.niveau_libelle AS niveau_diplome,
            f.experience_min_annees,
            f.experience_max_annees,
            f.salaire_min,
            f.salaire_max,
            f.devise,
            f.salaire_min_mensuel_eur,
            f.salaire_max_mensuel_eur,
            f.competences,
            f.langues,
            f.missions,
            f.description_brute,
            dp.date_jour AS date_publication,
            f.url,
            f.quality_score,
            (f.embedding <=> CAST(:vec AS analytics.vector)) AS distance,
            COALESCE(
                (SELECT array_agg(dt.tech_nom)
                   FROM analytics.bridge_offer_technologie b
                   JOIN analytics.dim_technologie dt ON dt.tech_id = b.tech_id
                  WHERE b.offer_id = f.offer_id AND dt.tech_id <> 0),
                '{{}}'::text[]
            ) AS technologies
        FROM analytics.fact_offer f
        JOIN analytics.dim_societe        soc ON soc.societe_id   = f.societe_id
        JOIN analytics.dim_ville          v   ON v.ville_id       = f.ville_id
        JOIN analytics.dim_pays           p   ON p.pays_id        = f.pays_id
        JOIN analytics.dim_metier         m   ON m.metier_id      = f.metier_id
        JOIN analytics.dim_contrat        c   ON c.contrat_id     = f.contrat_id
        JOIN analytics.dim_seniorite      sen ON sen.seniorite_id = f.seniorite_id
        JOIN analytics.dim_teletravail    t   ON t.teletravail_id = f.teletravail_id
        JOIN analytics.dim_niveau_diplome nd  ON nd.niveau_id     = f.niveau_diplome_id
        JOIN analytics.dim_date           dp  ON dp.date_id       = f.date_publication_id
        WHERE {where_clause}
        ORDER BY f.embedding <=> CAST(:vec AS analytics.vector)
        LIMIT :limit
    """

    # Raise IVFFlat probes so the ANN scan visits enough lists. With the
    # default probes=1 we'd only see ~1/100 of the vectors.
    await session.execute(sql_text("SET LOCAL ivfflat.probes = 10"))
    result = await session.execute(sql_text(query), params)
    return [dict(row._mapping) for row in result]


def _rerank(
    profile: ProfilePayload,
    candidates: List[dict],
    top_k: int,
) -> List[RecommendedOffer]:
    user_tech = _normalize_set(profile.tech_stack) | _normalize_set(profile.competences)
    user_langs = _normalize_set(profile.langues)
    w = settings

    scored: List[RecommendedOffer] = []
    for row in candidates:
        # Canonical tech set: bridge tags + extractor hits on the free-text
        # description and competences[] / missions[] arrays. The extractor
        # returns lowercase canonical names so they merge cleanly.
        bridge_tech = _normalize_set(row.get("technologies"))
        free_text_blobs: List[str] = []
        for arr_key in ("competences", "missions"):
            arr = row.get(arr_key) or []
            free_text_blobs.extend(str(s) for s in arr if s)
        desc = row.get("description_brute") or ""
        if desc:
            # Cap so the regex doesn't churn on multi-page descriptions.
            free_text_blobs.append(desc[:6000])
        extracted_tech = tech_extractor.extract_from_many(free_text_blobs)
        offer_tech = bridge_tech | extracted_tech
        offer_langs = _normalize_set(row.get("langues"))

        vector_sim = max(0.0, 1.0 - float(row["distance"]))
        tech_sc, matched, missing = _tech_overlap(user_tech, offer_tech)

        offer = OfferOut(
            offer_id=row["offer_id"],
            poste=row["poste"],
            titre_original=row.get("titre_original"),
            societe_nom=row.get("societe_nom"),
            ville_nom=row.get("ville_nom"),
            pays_nom=row.get("pays_nom"),
            metier_libelle=row.get("metier_libelle"),
            contrat_libelle=row.get("contrat_libelle"),
            seniorite_libelle=row.get("seniorite_libelle"),
            teletravail_libelle=row.get("teletravail_libelle"),
            niveau_diplome=row.get("niveau_diplome"),
            experience_min_annees=row.get("experience_min_annees") or 0,
            experience_max_annees=row.get("experience_max_annees") or 0,
            salaire_min=row.get("salaire_min"),
            salaire_max=row.get("salaire_max"),
            devise=row.get("devise"),
            salaire_min_mensuel_eur=row.get("salaire_min_mensuel_eur") or 0,
            salaire_max_mensuel_eur=row.get("salaire_max_mensuel_eur") or 0,
            competences=list(row.get("competences") or []),
            langues=list(row.get("langues") or []),
            date_publication=row.get("date_publication"),
            url=row.get("url"),
            quality_score=row.get("quality_score") or 0,
        )

        # Active signals only: missing ones are dropped, weights renormalized.
        signals: List[Tuple[float, float, str]] = []  # (value, weight, name)
        signals.append((vector_sim, w.RECO_WEIGHT_VECTOR, "vector"))
        if user_tech:
            signals.append((tech_sc, w.RECO_WEIGHT_TECH_OVERLAP, "tech"))
        for val, weight, name in (
            (_seniority_score(profile.seniority, offer.seniorite_libelle),
             w.RECO_WEIGHT_SENIORITY, "seniority"),
            (_contract_score(profile.contrats, offer.contrat_libelle),
             w.RECO_WEIGHT_CONTRACT, "contract"),
            (_location_score(profile, offer), w.RECO_WEIGHT_LOCATION, "location"),
            (_remote_score(profile, offer), w.RECO_WEIGHT_REMOTE, "remote"),
            (_language_score(user_langs, offer_langs), w.RECO_WEIGHT_LANGUAGE, "language"),
        ):
            if val is not None:
                signals.append((val, weight, name))

        total_w = sum(weight for _, weight, _ in signals)
        base = sum(val * weight for val, weight, _ in signals) / total_w

        # Small additive boosts: freshness and offer quality
        q_boost = _quality_score(offer.quality_score) * 0.05
        f_val = _freshness_score(offer.date_publication)
        f_boost = f_val * 0.05 if f_val is not None else 0.0
        score = min(1.0, base + q_boost + f_boost)

        # Breakdown — show 0.0 for inactive signals (not 0.5).
        active = {name: val for val, _, name in signals}
        scored.append(RecommendedOffer(
            offer=offer,
            score=round(score, 4),
            breakdown=ScoreBreakdown(
                vector=round(active.get("vector", vector_sim), 4),
                tech_overlap=round(active.get("tech", 0.0), 4),
                seniority=round(active.get("seniority", 0.0), 4),
                contract=round(active.get("contract", 0.0), 4),
                location=round(active.get("location", 0.0), 4),
                remote=round(active.get("remote", 0.0), 4),
                language=round(active.get("language", 0.0), 4),
            ),
            matched_technologies=matched,
            missing_technologies=missing[:10],
        ))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]


async def recommend(
    session: AsyncSession,
    request: RecommendationRequest,
) -> List[RecommendedOffer]:
    profile = ProfilePayload.from_form(request.profile)
    embedding = await embed_one(profile.embedding_text())
    candidates = await _retrieve_candidates(session, embedding, request)
    if not candidates:
        return []
    return _rerank(profile, candidates, request.top_k)


async def recommend_from_payload(
    session: AsyncSession,
    profile: ProfilePayload,
    top_k: int = settings.RECO_DEFAULT_TOP_K,
    only_pays: Optional[List[str]] = None,
    min_salary_eur: Optional[int] = None,
    only_remote: bool = False,
    precomputed_embedding: Optional[List[float]] = None,
) -> List[RecommendedOffer]:
    """Variant for CV-derived profiles (no form object).

    If `precomputed_embedding` is provided, skip the model encode step.
    """
    from app.schemas.profile import ProfileForm

    fake = RecommendationRequest(
        profile=ProfileForm(
            poste_recherche=profile.poste_recherche,
            metier_code=profile.metier_code,
            seniority=profile.seniority,
            annees_experience=profile.annees_experience,
            tech_stack=profile.tech_stack,
            competences=profile.competences,
            langues=profile.langues,
            contrats=profile.contrats,
            remote=profile.remote,
            villes=profile.villes,
            pays=profile.pays,
            salaire_min_mensuel_eur=profile.salaire_min_mensuel_eur,
            description_libre=profile.raw_text,
        ),
        top_k=top_k,
        only_pays=only_pays,
        min_salary_eur=min_salary_eur,
        only_remote=only_remote,
    )
    vec = precomputed_embedding or await embed_one(profile.embedding_text())
    candidates = await _retrieve_candidates(session, vec, fake)
    if not candidates:
        return []
    return _rerank(profile, candidates, top_k)
