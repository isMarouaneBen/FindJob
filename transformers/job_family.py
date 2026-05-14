"""
Classification métier (job family) à partir du titre + description + skills.

Sortie : un code court parmi un référentiel fermé, qui alimente `dim_metier`.
Sert à :
- Filtrer / regrouper les offres dans Power BI (Data, Dev, Cloud, etc.).
- Système de recommandation : agrège les profils similaires plus efficacement
  qu'avec des keywords libres.

Approche : règles pondérées (mots-clés). Pas de ML embarqué : maintenable,
explicable, et suffisant tant que le périmètre reste tech francophone.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Référentiel métier — code, libellé, ordre d'affichage.
# Le code "DATA_SCI" inclut ML/IA, "DATA_ENG" le pipeline, "DATA_ANA" l'analyse.
METIERS: list[tuple[str, str, int]] = [
    ("DATA_SCI",   "Data Scientist / ML",      10),
    ("DATA_ENG",   "Data Engineer",            20),
    ("DATA_ANA",   "Data Analyst",             30),
    ("BI",         "Business Intelligence",    40),
    ("DATA_ARCH",  "Data Architect",           50),
    ("DEVOPS",     "DevOps / SRE",             60),
    ("CLOUD",      "Cloud Engineer",           70),
    ("CYBER",      "Cybersécurité",            80),
    ("DEV_BACK",   "Développeur Backend",      90),
    ("DEV_FRONT",  "Développeur Frontend",    100),
    ("DEV_FULL",   "Développeur Fullstack",   110),
    ("DEV_MOBILE", "Développeur Mobile",      120),
    ("ADMIN_SYS",  "Admin Système / Réseau",  130),
    ("MGT",        "Management / Direction",  140),
    ("PRODUCT",    "Product / Projet",        150),
    ("CONSULT",    "Consultant",              160),
    ("AUTRE",      "Autre",                   999),
]

# Patterns ordonnés : le 1er match gagne. Casses-pièges en haut.
# Score = poids en cas de match (titre vaut plus que description).
_RULES: list[tuple[str, list[tuple[re.Pattern[str], int]]]] = [
    ("DATA_ARCH", [
        (re.compile(r"\barchitecte?\s+(?:de\s+)?(?:donn[ée]e|data)", re.I), 10),
        (re.compile(r"\bdata\s+architect", re.I), 10),
    ]),
    ("DATA_SCI", [
        (re.compile(r"\bdata\s+scientist", re.I), 10),
        (re.compile(r"\bml\s+engineer", re.I), 10),
        (re.compile(r"\bmachine\s+learning\s+engineer", re.I), 10),
        (re.compile(r"\b(ia|ai)\s+engineer", re.I), 8),
        (re.compile(r"\b(machine\s+learning|deep\s+learning|nlp|computer\s+vision)\b", re.I), 4),
    ]),
    ("DATA_ENG", [
        (re.compile(r"\bdata\s+engineer", re.I), 10),
        (re.compile(r"\bbig\s+data\s+engineer", re.I), 10),
        (re.compile(r"\b(etl|elt)\s+(developer|developpeur)", re.I), 8),
        (re.compile(r"\bingenieur\s+(de\s+)?donn[ée]es", re.I), 8),
        (re.compile(r"\b(spark|kafka|airflow|databricks|snowflake)\b", re.I), 2),
    ]),
    ("DATA_ANA", [
        (re.compile(r"\bdata\s+analyst", re.I), 10),
        (re.compile(r"\banalyste?\s+(de\s+)?donn[ée]es", re.I), 8),
        (re.compile(r"\bbusiness\s+analyst", re.I), 6),
    ]),
    ("BI", [
        (re.compile(r"\bbusiness\s+intelligence", re.I), 10),
        (re.compile(r"\bbi\s+(developer|developpeur|consultant|analyst)", re.I), 10),
        (re.compile(r"\b(power\s*bi|tableau|qlik)\b.*?(consultant|developer|developpeur)", re.I), 8),
    ]),
    ("DEVOPS", [
        (re.compile(r"\bdevops\b", re.I), 10),
        (re.compile(r"\b(sre|site\s+reliability)\b", re.I), 10),
        (re.compile(r"\bplatform\s+engineer", re.I), 8),
    ]),
    ("CLOUD", [
        (re.compile(r"\bcloud\s+(engineer|architect|consultant)", re.I), 10),
        (re.compile(r"\b(aws|azure|gcp)\s+(engineer|architect|consultant)", re.I), 9),
    ]),
    ("CYBER", [
        (re.compile(r"\b(cybers[eé]curit[eé]|security\s+engineer|pentester|soc\s+analyst)", re.I), 10),
        (re.compile(r"\bingenieur\s+s[eé]curit[eé]", re.I), 9),
    ]),
    ("DEV_FULL", [
        (re.compile(r"\b(full[\s-]?stack)\b", re.I), 10),
    ]),
    ("DEV_BACK", [
        (re.compile(r"\b(back[\s-]?end|backend)\b.*?(developer|developpeur|engineer|ingenieur)", re.I), 10),
        (re.compile(r"\b(java|spring|python|django|flask|node)\s+(developer|developpeur)", re.I), 6),
    ]),
    ("DEV_FRONT", [
        (re.compile(r"\b(front[\s-]?end|frontend)\b.*?(developer|developpeur|engineer|ingenieur)", re.I), 10),
        (re.compile(r"\b(react|angular|vue)\s+(developer|developpeur)", re.I), 6),
    ]),
    ("DEV_MOBILE", [
        (re.compile(r"\b(mobile|android|ios)\s+(developer|developpeur)", re.I), 10),
        (re.compile(r"\b(react\s*native|flutter)\b", re.I), 6),
    ]),
    ("ADMIN_SYS", [
        (re.compile(r"\b(administrateur|admin)\s+(syst[eè]me|r[eé]seau|infrastructure)", re.I), 10),
        (re.compile(r"\b(ingenieur|technicien)\s+r[eé]seau", re.I), 8),
        (re.compile(r"\bsystem[s]?\s+administrator", re.I), 9),
    ]),
    ("PRODUCT", [
        (re.compile(r"\bproduct\s+(owner|manager)", re.I), 10),
        (re.compile(r"\bscrum\s+master", re.I), 9),
        (re.compile(r"\bchef\s+de\s+projet", re.I), 9),
        (re.compile(r"\bproject\s+manager", re.I), 8),
    ]),
    ("MGT", [
        (re.compile(r"\b(directeur|director|head\s+of|cto|cio|chief)\b", re.I), 10),
        (re.compile(r"\b(manager|responsable)\b", re.I), 5),
    ]),
    ("CONSULT", [
        (re.compile(r"\bconsultant\b", re.I), 8),
    ]),
    ("DEV_BACK", [
        (re.compile(r"\b(developpeur|developer)\b", re.I), 4),
        (re.compile(r"\b(software|software)\s+engineer", re.I), 4),
    ]),
]


def _norm(text: str | None) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return s.lower()


def classify(
    titre: str | None,
    description: str | None = None,
    skills: Iterable[str] | None = None,
) -> str:
    """Renvoie le code métier (`AUTRE` si rien ne matche)."""
    titre_n = _norm(titre or "")
    desc_n  = _norm(description or "")

    scores: dict[str, int] = {}
    for code, rules in _RULES:
        for pat, weight in rules:
            if pat.search(titre_n):
                scores[code] = scores.get(code, 0) + weight * 3
            elif pat.search(desc_n):
                scores[code] = scores.get(code, 0) + weight

    if not scores:
        return "AUTRE"
    return max(scores.items(), key=lambda kv: kv[1])[0]
