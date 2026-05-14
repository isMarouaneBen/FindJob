"""
Enrichissements communs aux 3 transformers.

Sortie : dict prêt à être fusionné dans le record final, contenant les
champs d'analyse et de recommandation :
    metier_code, salaire_min_mensuel_eur, salaire_max_mensuel_eur,
    salaire_min_mensuel_mad, salaire_max_mensuel_mad,
    quality_score (0-100), content_hash (16 chars).

Hypothèses devises :
- Adzuna FR : salaire stocké en EUR / annuel brut → mensuel = annuel / 12.
- Rekrute / Emploi-Public MA : salaire en MAD / mensuel → tel quel.
- Conversion EUR <-> MAD via constante (10.9, alignée avec salary_estimator).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Iterable

from job_family import classify
from salary_estimator import EUR_TO_MAD


# --------------------------------------------------------------------------- #
# Salaire : normalisation au mensuel + conversion croisée
# --------------------------------------------------------------------------- #

def normalize_salary(
    sal_min: float | int | None,
    sal_max: float | int | None,
    devise: str | None,
    source_id: int,
) -> dict[str, float | None]:
    """
    Renvoie un dict {salaire_min_mensuel_eur, salaire_max_mensuel_eur,
                     salaire_min_mensuel_mad, salaire_max_mensuel_mad}.
    Les valeurs sont arrondies à l'entier (None si inconnu).
    """
    out = {
        "salaire_min_mensuel_eur": None,
        "salaire_max_mensuel_eur": None,
        "salaire_min_mensuel_mad": None,
        "salaire_max_mensuel_mad": None,
    }
    if not sal_min and not sal_max:
        return out

    lo = float(sal_min or 0)
    hi = float(sal_max or sal_min or 0)
    code = (devise or "").upper().strip()

    if code == "EUR":
        # EUR annuel (Adzuna) → mensuel
        eur_min_m = lo / 12.0
        eur_max_m = hi / 12.0
    elif code == "MAD":
        # MAD mensuel
        mad_min_m = lo
        mad_max_m = hi
        eur_min_m = mad_min_m / EUR_TO_MAD
        eur_max_m = mad_max_m / EUR_TO_MAD
        out["salaire_min_mensuel_mad"] = round(mad_min_m)
        out["salaire_max_mensuel_mad"] = round(mad_max_m)
        out["salaire_min_mensuel_eur"] = round(eur_min_m)
        out["salaire_max_mensuel_eur"] = round(eur_max_m)
        return out
    else:
        return out

    out["salaire_min_mensuel_eur"] = round(eur_min_m)
    out["salaire_max_mensuel_eur"] = round(eur_max_m)
    out["salaire_min_mensuel_mad"] = round(eur_min_m * EUR_TO_MAD)
    out["salaire_max_mensuel_mad"] = round(eur_max_m * EUR_TO_MAD)
    return out


# --------------------------------------------------------------------------- #
# Quality score : 0-100, somme pondérée de signaux
# --------------------------------------------------------------------------- #

_QUALITY_WEIGHTS: list[tuple[str, int]] = [
    ("poste",            10),
    ("societe",          10),
    ("ville",            10),
    ("type_contrat",      8),
    ("seniorite",         5),
    ("diplome_niveau",    5),
    ("experience",        5),
    ("salaire_explicite", 12),
    ("technologies",     10),
    ("missions",          8),
    ("competences",       7),
    ("description_riche", 5),
    ("date_publication",  5),
]


def quality_score(rec: dict[str, Any]) -> int:
    """Score 0-100 : combien de champs utiles sont présents et substantiels."""
    score = 0
    if (rec.get("poste") or "").strip():
        score += 10
    if (rec.get("societe") or "").strip():
        score += 10
    if rec.get("villes") or rec.get("ville_principale"):
        score += 10
    if (rec.get("type_contrat") or "").strip():
        score += 8
    if rec.get("seniorite") or rec.get("experience_label"):
        score += 5
    if (rec.get("diplome_niveau") or "").strip():
        score += 5
    if rec.get("experience_min_annees") is not None:
        score += 5
    if rec.get("source_salaire") == "source":
        score += 12  # salaire explicite (pas estimation)
    if len(rec.get("technologies") or []) >= 1:
        score += 10
    if len(rec.get("missions") or []) >= 1:
        score += 8
    if len(rec.get("competences") or []) >= 1:
        score += 7
    desc = rec.get("description_brute") or ""
    if len(desc) >= 400:
        score += 5
    if rec.get("date_publication") or rec.get("date_debut"):
        score += 5
    return min(score, 100)


# --------------------------------------------------------------------------- #
# Content hash : dédoublonnage cross-source
# --------------------------------------------------------------------------- #

_NOISE_RE = re.compile(r"\W+")


def _hash_key(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return _NOISE_RE.sub("", s.lower())


def content_hash(rec: dict[str, Any]) -> str:
    """
    Hash stable pour détecter les doublons inter-sources.
    Combine poste + société + 1ère ville (clés normalisées sans bruit).
    16 hex = collisions négligeables sur un corpus de quelques milliers de lignes.
    """
    poste = _hash_key(rec.get("poste") or rec.get("titre_original") or "")
    soc   = _hash_key(rec.get("societe") or "")
    ville = ""
    if rec.get("ville_principale"):
        ville = _hash_key(rec["ville_principale"])
    elif rec.get("villes"):
        ville = _hash_key((rec["villes"] or [""])[0])
    raw = f"{poste}|{soc}|{ville}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Cleanup bullets (missions / compétences) : dédup sémantique
# --------------------------------------------------------------------------- #

_BULLET_BOILERPLATE = re.compile(
    r"^(rejoignez|nous (sommes|recrutons|recherchons)|notre (client|cabinet)|"
    r"vous (êtes|seriez|serez)|au sein de|le poste|en tant que|"
    r"votre profil|profil recherch[ée]|description du poste|descriptif|"
    r"merci d'envoyer|inscrivez-vous|connectez-vous)",
    re.IGNORECASE,
)


def clean_bullets(items: Iterable[str] | None, *, max_items: int = 30,
                  max_len: int = 500) -> list[str]:
    """Nettoie une liste de puces : dédup, retire boilerplate, longueur min/max."""
    if not items:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        if not raw:
            continue
        s = re.sub(r"\s+", " ", str(raw)).strip(" .,;:-•·")
        if len(s) < 8 or len(s) > max_len:
            continue
        if _BULLET_BOILERPLATE.match(s):
            continue
        key = re.sub(r"\W+", "", s.lower())[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_items:
            break
    return out


# --------------------------------------------------------------------------- #
# API d'orchestration
# --------------------------------------------------------------------------- #

def enrich(rec: dict[str, Any], source_id: int) -> dict[str, Any]:
    """
    Calcule tous les champs dérivés (in-place) et les renvoie.
    À appeler à la fin de chaque transformer, juste avant la sortie.
    """
    rec["missions"]    = clean_bullets(rec.get("missions"),    max_items=25, max_len=2000)
    rec["competences"] = clean_bullets(rec.get("competences"), max_items=20, max_len=500)

    rec["metier_code"] = classify(
        titre=rec.get("titre_original") or rec.get("poste"),
        description=rec.get("description_brute"),
        skills=rec.get("technologies") or [],
    )
    salnorm = normalize_salary(
        rec.get("salaire_min"), rec.get("salaire_max"),
        rec.get("devise"), source_id,
    )
    rec.update(salnorm)
    rec["quality_score"] = quality_score(rec)
    rec["content_hash"]  = content_hash(rec)
    return rec
