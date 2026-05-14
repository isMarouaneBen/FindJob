"""
Normalisation géographique partagée par tous les transformers / ETL.

Objectif : éviter que des noms de pays, régions ou départements français se
retrouvent dans `dim_ville`. Adzuna renvoie un tableau `location_area` ordonné
[pays, région, département, ..., ville] mais quand l'annonce est très large
on n'a parfois que `["France"]` ou `["France", "Île-de-France"]` — sans ce
filtre, "France" et "Île-de-France" deviennent des villes dans le DWH.
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------- #
# Sets : pays / régions / départements à ne JAMAIS considérer comme villes
# --------------------------------------------------------------------------- #

_COUNTRIES = {
    "france", "maroc", "morocco", "algerie", "tunisie", "espagne", "spain",
    "belgique", "belgium", "suisse", "switzerland", "luxembourg",
    "royaume-uni", "united kingdom", "uk", "allemagne", "germany",
    "italie", "italy", "portugal", "pays-bas", "netherlands", "canada",
}

_FRENCH_REGIONS = {
    "auvergne-rhone-alpes", "auvergne rhone alpes",
    "bourgogne-franche-comte", "bourgogne franche comte",
    "bretagne",
    "centre-val de loire", "centre val de loire",
    "corse",
    "grand est",
    "hauts-de-france", "hauts de france",
    "ile-de-france", "ile de france", "île-de-france", "île de france",
    "normandie",
    "nouvelle-aquitaine", "nouvelle aquitaine",
    "occitanie",
    "pays de la loire",
    "provence-alpes-cote d'azur", "provence alpes cote d azur", "paca",
    # DROM-COM
    "guadeloupe", "martinique", "guyane", "la reunion", "mayotte",
}

# Liste des 101 départements français (forme accentuée / non accentuée acceptée)
_FRENCH_DEPARTEMENTS = {
    "ain", "aisne", "allier", "alpes-de-haute-provence", "hautes-alpes",
    "alpes-maritimes", "ardeche", "ardennes", "ariege", "aube", "aude",
    "aveyron", "bouches-du-rhone", "calvados", "cantal", "charente",
    "charente-maritime", "cher", "correze", "corse-du-sud", "haute-corse",
    "cote-d'or", "cote d or", "cotes-d'armor", "cotes d armor",
    "creuse", "dordogne", "doubs", "drome", "eure", "eure-et-loir",
    "finistere", "gard", "haute-garonne", "gers", "gironde", "herault",
    "ille-et-vilaine", "indre", "indre-et-loire", "isere", "jura",
    "landes", "loir-et-cher", "loire", "haute-loire", "loire-atlantique",
    "loiret", "lot", "lot-et-garonne", "lozere", "maine-et-loire",
    "manche", "marne", "haute-marne", "mayenne", "meurthe-et-moselle",
    "meuse", "morbihan", "moselle", "nievre", "nord", "oise", "orne",
    "pas-de-calais", "puy-de-dome", "pyrenees-atlantiques",
    "hautes-pyrenees", "pyrenees-orientales", "bas-rhin", "haut-rhin",
    "rhone", "haute-saone", "saone-et-loire", "sarthe", "savoie",
    "haute-savoie",
    # Note : "Paris" est à la fois département (75) ET ville. On le garde donc
    # comme ville et on ne l'inclut PAS dans cette blacklist.
    "seine-maritime", "seine-et-marne", "yvelines", "deux-sevres", "somme",
    "tarn", "tarn-et-garonne", "var", "vaucluse", "vendee", "vienne",
    "haute-vienne", "vosges", "yonne", "territoire de belfort",
    "essonne", "hauts-de-seine", "seine-saint-denis", "val-de-marne",
    "val-d'oise", "val d oise",
}

_NON_VILLE = _COUNTRIES | _FRENCH_REGIONS | _FRENCH_DEPARTEMENTS


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _key(text: str) -> str:
    """Forme canonique pour comparaison : lowercase, sans accents, espaces normalisés."""
    s = _strip_accents(text or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


# --------------------------------------------------------------------------- #
# API publique
# --------------------------------------------------------------------------- #

def is_non_ville(name: str | None) -> bool:
    """True si `name` est un pays / région / département (pas une ville)."""
    if not name:
        return True
    return _key(name) in _NON_VILLE


# Arrondissements / cantons : on ramène à la ville-mère
_PARIS_ARR_RE = re.compile(r"^\s*(\d{1,2})\s*(?:er|e|ème|eme|nd|nde)?[\s\-]+arrondissement\s*$",
                            re.IGNORECASE)
_LYON_ARR_RE = re.compile(r"^lyon\s+\d{1,2}\s*(?:er|e|ème|eme)?$", re.IGNORECASE)
_MARSEILLE_ARR_RE = re.compile(r"^marseille\s+\d{1,2}\s*(?:er|e|ème|eme)?$", re.IGNORECASE)
_CANTON_RE = re.compile(r"^(.+?)\s+\d{1,2}\s*(?:er|e|ème|eme)?\s*canton(?:\s+\S+)?$",
                         re.IGNORECASE)


def normalize_ville(name: str | None) -> str | None:
    """
    Renvoie un nom de ville propre OU None si l'entrée n'est pas une ville
    (pays, région, département, vide, ...).

    - Trim + collapse espaces.
    - Mappe "8ème Arrondissement" / "1er-Arrondissement" → "Paris".
    - Mappe "Lyon 3", "Marseille 9e" → "Lyon" / "Marseille".
    - Mappe "Cholet 1er Canton" → "Cholet".
    - Renvoie None pour France / Île-de-France / Hauts-de-Seine / etc.
    """
    if not name:
        return None
    s = re.sub(r"\s+", " ", str(name)).strip(" ,;-\t\n")
    if not s:
        return None

    # Arrondissements parisiens (sans préfixe de ville → Paris)
    if _PARIS_ARR_RE.match(s):
        return "Paris"
    if _LYON_ARR_RE.match(s):
        return "Lyon"
    if _MARSEILLE_ARR_RE.match(s):
        return "Marseille"

    # "X 1er Canton" → "X"
    m = _CANTON_RE.match(s)
    if m:
        s = m.group(1).strip()

    if is_non_ville(s):
        return None

    # Limite de longueur défensive (le schéma autorise 160 chars).
    return s[:160]


def normalize_villes(values) -> list[str]:
    """Applique `normalize_ville` à une liste, déduplique en gardant l'ordre."""
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        cleaned = normalize_ville(v)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def pick_city_from_area(area) -> str | None:
    """
    Pour le tableau `location_area` d'Adzuna ([pays, région, dept, ..., ville]),
    prend l'élément le plus spécifique qui n'est PAS un pays/région/département.
    Renvoie None si tout est blacklisté (annonce nationale type ["France"]).
    """
    if not area:
        return None
    for item in reversed(list(area)):
        cleaned = normalize_ville(item)
        if cleaned:
            return cleaned
    return None
