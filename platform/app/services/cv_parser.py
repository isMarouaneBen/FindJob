"""
CV parsing: bytes → text → ProfilePayload.

Extracts as much as possible from the raw text:
  • role / desired position (regex on the head + fallback to first non-trivial line)
  • years of experience
  • seniority (heuristic, from years + keywords)
  • canonical technologies (via tech_extractor, with aliases)
  • spoken languages
  • education level (Bac+5, Master, Engineer, PhD, …) → niveau code
  • city / country (intersected with dim_ville / dim_pays)
  • contract preferences (CDI / CDD / Stage / Alternance / Freelance)
  • remote preference
  • email / phone (kept in raw_text but not exposed as structured fields)
"""
from __future__ import annotations

import io
import logging
import re
from typing import List, Optional, Set

from app.schemas.profile import (
    ContractType,
    ProfilePayload,
    RemotePreference,
    SeniorityLevel,
)
from app.services import tech_extractor

logger = logging.getLogger(__name__)


LANGUAGE_VOCAB = {
    "français", "francais", "anglais", "arabe", "espagnol", "allemand",
    "italien", "portugais", "english", "french", "arabic", "spanish",
    "german", "italian", "portuguese", "chinois", "chinese",
}


# ---------- file → text ----------------------------------------------------

def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    import docx  # python-docx

    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
    # Some PDFs emit ligatures as ASCII control bytes (observed: \x1c/\x1d
    # for fi/fl when the font has no plain replacement glyph).
    "\x1c": "fi", "\x1d": "fl",
    "­": "",  # soft hyphen
}


def _normalize_pdf_artifacts(text: str) -> str:
    """Repair the most common pypdf extraction defects.

    - Map ligature codepoints to their ASCII spelling so "Snowﬂake" /
      "Sno\x1dake" both become "Snowflake".
    - Collapse runs of single-character "words" separated by single spaces
      back into one word: "P o w er BI" → "Power BI", "Do c k er" → "Docker".
      A pure single-letter run of length ≥ 2 is treated as one broken word.
    """
    for src, dst in _LIGATURES.items():
        text = text.replace(src, dst)

    # First pass: collapse "letter SPACE letter SPACE letter…" runs.
    def _join_letters(m: re.Match) -> str:
        return m.group(0).replace(" ", "")
    text = re.sub(r"\b(?:[A-Za-z]\s){2,}[A-Za-z]\b", _join_letters, text)

    return text


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        raw = _extract_pdf(data)
    elif name.endswith(".docx"):
        raw = _extract_docx(data)
    elif name.endswith(".txt"):
        raw = data.decode("utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported CV format: {filename}")
    return _normalize_pdf_artifacts(raw)


# ---------- field extractors ----------------------------------------------

_ROLE_HINT = re.compile(
    r"\b(senior\s+)?("
    r"data\s+(?:scientist|engineer|analyst|architect|steward)"
    r"|(?:machine\s+learning|ml|ai|gen\s*ai)\s+engineer"
    r"|devops(?:\s+engineer)?|sre|cloud\s+(?:engineer|architect)"
    r"|(?:back|front)[-\s]?end\s+developer|full[-\s]?stack\s+developer"
    r"|software\s+engineer|developer|développeur(?:\s+\w+)?"
    r"|ingénieur(?:\s+\w+){0,3}"
    r"|product\s+manager|business\s+(?:analyst|intelligence)"
    r"|consultant(?:\s+\w+)?|architecte(?:\s+\w+)?"
    r"|administrateur(?:\s+systèmes?| réseau)?|sysadmin"
    r")\b",
    re.IGNORECASE,
)


def _guess_role(text: str) -> Optional[str]:
    head = text[:2000]
    m = _ROLE_HINT.search(head)
    if m:
        return re.sub(r"\s+", " ", m.group(0)).strip().title()
    for line in head.splitlines():
        line = line.strip()
        if 4 <= len(line) <= 80 and not any(c in line for c in "@:/0123456789"):
            return line
    return None


_LANG_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in LANGUAGE_VOCAB) + r")\b",
    re.IGNORECASE,
)


def _extract_languages(text: str) -> List[str]:
    found = {m.group(0).lower() for m in _LANG_RE.finditer(text)}
    # Normalise francais → français, english → anglais, etc.
    norm = {
        "francais": "français", "english": "anglais", "french": "français",
        "arabic": "arabe", "spanish": "espagnol", "german": "allemand",
        "italian": "italien", "portuguese": "portugais", "chinese": "chinois",
    }
    return sorted({norm.get(w, w) for w in found})


_YEARS_RE = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:ans|years?|année|annee)\b", re.IGNORECASE
)


def _extract_years(text: str) -> int:
    best = 0
    for m in _YEARS_RE.finditer(text):
        try:
            best = max(best, int(m.group(1)))
        except ValueError:
            continue
    return min(best, 50)


def _guess_seniority(years: int, text: str) -> Optional[SeniorityLevel]:
    low = text.lower()
    if "stage" in low or "internship" in low or "intern " in low:
        return SeniorityLevel.STAGE
    if "alternance" in low or "apprentice" in low:
        return SeniorityLevel.ALTERNANCE
    if years == 0:
        return SeniorityLevel.JUNIOR
    if years <= 2:
        return SeniorityLevel.JUNIOR
    if years <= 4:
        return SeniorityLevel.INTERMEDIAIRE
    if years <= 6:
        return SeniorityLevel.CONFIRME
    if years <= 9:
        return SeniorityLevel.SENIOR
    return SeniorityLevel.EXPERT


# Education ----------------------------------------------------------------

_EDU_PATTERNS = [
    (re.compile(r"\b(?:phd|ph\.d\.?|doctorat)\b", re.I),       "Doctorat"),
    (re.compile(r"\b(?:bac\s*\+\s*5|master|m\.?\s*sc|mba|ingénieur(?:e)?)\b", re.I), "Bac+5"),
    (re.compile(r"\b(?:bac\s*\+\s*4)\b", re.I),                "Bac+4"),
    (re.compile(r"\b(?:bac\s*\+\s*3|licence|bachelor|b\.?\s*sc)\b", re.I), "Bac+3"),
    (re.compile(r"\b(?:bac\s*\+\s*2|dut|bts)\b", re.I),        "Bac+2"),
    (re.compile(r"\bbac(?:calauréat)?\b", re.I),                "Bac"),
]


def _extract_education(text: str) -> Optional[str]:
    for pat, code in _EDU_PATTERNS:
        if pat.search(text):
            return code
    return None


# Contracts / remote -------------------------------------------------------

_CONTRACT_HINTS = {
    "cdi": ContractType.CDI,
    "cdd": ContractType.CDD,
    "stage": ContractType.STAGE,
    "internship": ContractType.STAGE,
    "intern": ContractType.STAGE,
    "alternance": ContractType.ALTERNANCE,
    "apprentice": ContractType.ALTERNANCE,
    "freelance": ContractType.FREELANCE,
    "indépendant": ContractType.FREELANCE,
    "self-employed": ContractType.FREELANCE,
    "intérim": ContractType.INTERIM,
    "interim": ContractType.INTERIM,
}


def _extract_contracts(text: str) -> List[ContractType]:
    low = text.lower()
    found: Set[ContractType] = set()
    for needle, ct in _CONTRACT_HINTS.items():
        if re.search(r"\b" + re.escape(needle) + r"\b", low):
            found.add(ct)
    return sorted(found, key=lambda c: c.value)


def _extract_remote(text: str) -> Optional[RemotePreference]:
    low = text.lower()
    if re.search(r"\b(?:100%\s*remote|fully\s*remote|full\s*remote|télétravail\s*total)\b", low):
        return RemotePreference.TOTAL
    if re.search(r"\bhybride|hybrid\b", low):
        return RemotePreference.HYBRIDE
    if re.search(r"\bremote\s*friendly|télétravail|home\s*office\b", low):
        return RemotePreference.POSSIBLE
    return None


# Country of residence -----------------------------------------------------
#
# We don't try to extract cities — only the candidate's residence country.
# Order of signals (first hit wins):
#   1. Phone number international prefix  ("+212 …" → Maroc)
#   2. Explicit phrase                    ("Résidant à Casablanca, Maroc",
#                                          "Based in Paris, France", …)
#   3. Address-like line                  (city + comma + country at the top)
#   4. City mention near the head of CV   → look up the city's country
#   5. Most-mentioned country in the doc  (fallback)

_COUNTRY_HINTS = {
    "france": "France", "maroc": "Maroc", "morocco": "Maroc",
    "algerie": "Algérie", "algérie": "Algérie", "algeria": "Algérie",
    "tunisie": "Tunisie", "tunisia": "Tunisie",
    "espagne": "Espagne", "spain": "Espagne",
    "belgique": "Belgique", "belgium": "Belgique",
    "suisse": "Suisse", "switzerland": "Suisse",
    "allemagne": "Allemagne", "germany": "Allemagne",
    "italie": "Italie", "italy": "Italie",
    "portugal": "Portugal",
    "luxembourg": "Luxembourg",
    "pays-bas": "Pays-Bas", "netherlands": "Pays-Bas",
    "royaume-uni": "Royaume-Uni", "united kingdom": "Royaume-Uni", "uk": "Royaume-Uni",
    "england": "Royaume-Uni",
    "canada": "Canada",
    "usa": "États-Unis", "united states": "États-Unis", "us": "États-Unis",
    "états-unis": "États-Unis", "etats-unis": "États-Unis",
    "émirats arabes unis": "Émirats Arabes Unis", "uae": "Émirats Arabes Unis",
    "dubai": "Émirats Arabes Unis", "abu dhabi": "Émirats Arabes Unis",
}

# International dialling code → country.
_PHONE_PREFIX = {
    "212": "Maroc",
    "33": "France",
    "32": "Belgique",
    "41": "Suisse",
    "49": "Allemagne",
    "44": "Royaume-Uni",
    "34": "Espagne",
    "39": "Italie",
    "351": "Portugal",
    "352": "Luxembourg",
    "31": "Pays-Bas",
    "213": "Algérie",
    "216": "Tunisie",
    "971": "Émirats Arabes Unis",
    "1": "États-Unis",  # also Canada — kept as a last-resort signal.
}

# Major cities → country, used for the soft city-based inference. Keep this
# tight; it's only consulted near the top of the CV.
_CITY_TO_COUNTRY = {
    # Maroc
    "casablanca": "Maroc", "rabat": "Maroc", "tanger": "Maroc",
    "marrakech": "Maroc", "fès": "Maroc", "fes": "Maroc",
    "agadir": "Maroc", "kenitra": "Maroc", "oujda": "Maroc",
    "tétouan": "Maroc", "tetouan": "Maroc", "salé": "Maroc",
    "meknès": "Maroc", "meknes": "Maroc",
    # France
    "paris": "France", "lyon": "France", "marseille": "France",
    "toulouse": "France", "bordeaux": "France", "nantes": "France",
    "lille": "France", "strasbourg": "France", "rennes": "France",
    "montpellier": "France", "nice": "France", "grenoble": "France",
    # Other
    "london": "Royaume-Uni", "madrid": "Espagne", "berlin": "Allemagne",
    "brussels": "Belgique", "geneva": "Suisse", "luxembourg": "Luxembourg",
    "amsterdam": "Pays-Bas", "dubai": "Émirats Arabes Unis",
    "abu dhabi": "Émirats Arabes Unis", "new york": "États-Unis",
    "montreal": "Canada", "toronto": "Canada",
}


_PHONE_RE = re.compile(r"\+\s*(\d{1,3})[\s\-./()]*\d")

_RESIDENCE_PHRASE = re.compile(
    r"\b(?:résidant\s*(?:à|en)|résident\s*(?:à|en)|domicili[ée]\s*(?:à|en)|"
    r"based\s+in|located\s+in|living\s+in|lives?\s+in|"
    r"address|adresse)\s*[:\-]?\s*([A-ZÀ-Ÿa-zà-ÿ\-\s,]+)",
    re.IGNORECASE,
)


def _country_from_phone(text: str) -> Optional[str]:
    for m in _PHONE_RE.finditer(text):
        prefix = m.group(1)
        # Try the longest prefix first (e.g. 212 wins over 21).
        for length in (3, 2, 1):
            cand = prefix[:length]
            if cand in _PHONE_PREFIX:
                return _PHONE_PREFIX[cand]
    return None


def _country_from_phrase(text: str) -> Optional[str]:
    for m in _RESIDENCE_PHRASE.finditer(text):
        snippet = m.group(1).lower()
        for needle, canon in _COUNTRY_HINTS.items():
            if re.search(r"\b" + re.escape(needle) + r"\b", snippet):
                return canon
        for city, country in _CITY_TO_COUNTRY.items():
            if re.search(r"\b" + re.escape(city) + r"\b", snippet):
                return country
    return None


def _country_from_head_city(text: str) -> Optional[str]:
    head = text[:1500].lower()
    for city, country in _CITY_TO_COUNTRY.items():
        if re.search(r"(?<![a-zé])" + re.escape(city) + r"(?![a-zé])", head):
            return country
    return None


def _country_by_frequency(text: str) -> Optional[str]:
    low = text.lower()
    counts: dict[str, int] = {}
    for needle, canon in _COUNTRY_HINTS.items():
        n = len(re.findall(r"\b" + re.escape(needle) + r"\b", low))
        if n:
            counts[canon] = counts.get(canon, 0) + n
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _extract_residence_country(text: str) -> Optional[str]:
    """Return the inferred country of residence, or None."""
    for fn in (_country_from_phone, _country_from_phrase,
               _country_from_head_city, _country_by_frequency):
        country = fn(text)
        if country:
            return country
    return None


# ---------- main entrypoint -----------------------------------------------

def parse_cv(filename: str, data: bytes, desired_role: Optional[str] = None) -> ProfilePayload:
    text = extract_text(filename, data)
    techs = sorted(tech_extractor.extract(text))
    langs = _extract_languages(text)
    years = _extract_years(text)
    seniority = _guess_seniority(years, text)
    role = desired_role or _guess_role(text) or "Candidate profile"
    residence = _extract_residence_country(text)
    pays = [residence] if residence else []
    contrats = _extract_contracts(text)
    remote = _extract_remote(text)
    education = _extract_education(text)

    logger.info(
        "CV %s: role=%r years=%s seniority=%s tech=%d langs=%s pays=%s edu=%s",
        filename, role, years, seniority.value if seniority else None,
        len(techs), langs, residence, education,
    )

    return ProfilePayload(
        poste_recherche=role,
        annees_experience=years,
        seniority=seniority,
        tech_stack=techs,
        competences=techs,
        langues=langs,
        pays=pays,
        contrats=contrats,
        remote=remote,
        raw_text=text[:8000],
    )
