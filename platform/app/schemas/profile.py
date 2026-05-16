"""
User profile schemas — input to the recommendation engine.

A profile can come from two sources:
  1. A form filled by the user (ProfileForm)
  2. A parsed CV uploaded to MinIO (CVProfile, produced by the CV worker)

Both converge into `ProfilePayload`, which the matching service consumes.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SeniorityLevel(str, Enum):
    STAGE = "Stage"
    ALTERNANCE = "Alternance"
    JUNIOR = "Junior"
    INTERMEDIAIRE = "Intermediaire"
    CONFIRME = "Confirme"
    SENIOR = "Senior"
    EXPERT = "Expert"


class ContractType(str, Enum):
    CDI = "CDI"
    CDD = "CDD"
    STAGE = "Stage"
    ALTERNANCE = "Alternance"
    FREELANCE = "Freelance"
    INTERIM = "Interim"


class RemotePreference(str, Enum):
    NON = "Non"
    HYBRIDE = "Hybride"
    TOTAL = "Total"
    POSSIBLE = "Possible"


class ProfileForm(BaseModel):
    """Form-based user profile."""

    poste_recherche: str = Field(..., min_length=2, max_length=200,
                                 description="Desired job title, e.g. 'Data Engineer'")
    metier_code: Optional[str] = Field(
        None,
        description="One of dim_metier.metier_code (DATA_ENG, DEV_BACK, ...)",
    )
    seniority: Optional[SeniorityLevel] = None
    annees_experience: int = Field(0, ge=0, le=50)
    tech_stack: List[str] = Field(
        default_factory=list,
        description="Technologies the user knows (Python, AWS, PostgreSQL...)",
    )
    competences: List[str] = Field(default_factory=list)
    langues: List[str] = Field(default_factory=list)
    contrats: List[ContractType] = Field(default_factory=list)
    remote: Optional[RemotePreference] = None
    villes: List[str] = Field(default_factory=list)
    pays: List[str] = Field(default_factory=list)
    salaire_min_mensuel_eur: Optional[int] = Field(None, ge=0)
    description_libre: Optional[str] = Field(
        None, max_length=4000,
        description="Free-text bio / job preferences — fed into the embedding",
    )

    @field_validator("tech_stack", "competences", "langues", "villes", "pays")
    @classmethod
    def _strip(cls, v: List[str]) -> List[str]:
        return [s.strip() for s in v if s and s.strip()]


class ProfilePayload(BaseModel):
    """
    Canonical profile representation used by the matching service.
    Either built from ProfileForm directly or produced by parsing a CV.
    """
    poste_recherche: str
    metier_code: Optional[str] = None
    seniority: Optional[SeniorityLevel] = None
    annees_experience: int = 0
    tech_stack: List[str] = Field(default_factory=list)
    competences: List[str] = Field(default_factory=list)
    langues: List[str] = Field(default_factory=list)
    contrats: List[ContractType] = Field(default_factory=list)
    remote: Optional[RemotePreference] = None
    villes: List[str] = Field(default_factory=list)
    pays: List[str] = Field(default_factory=list)
    salaire_min_mensuel_eur: Optional[int] = None
    raw_text: Optional[str] = None  # full CV text, if any

    @classmethod
    def from_form(cls, form: ProfileForm) -> "ProfilePayload":
        return cls(
            poste_recherche=form.poste_recherche,
            metier_code=form.metier_code,
            seniority=form.seniority,
            annees_experience=form.annees_experience,
            tech_stack=form.tech_stack,
            competences=form.competences,
            langues=form.langues,
            contrats=form.contrats,
            remote=form.remote,
            villes=form.villes,
            pays=form.pays,
            salaire_min_mensuel_eur=form.salaire_min_mensuel_eur,
            raw_text=form.description_libre,
        )

    def embedding_text(self) -> str:
        """Build the text used to embed the profile. Mirrors the offer-side
        builder: title duplicated for weight, then structured fields, then
        the bulk of the free-text CV body. Output is capped to ~4000 chars,
        comfortably under the model's 512-token window."""
        parts: List[str] = []
        if self.poste_recherche and self.poste_recherche != "Candidate profile":
            parts.extend([self.poste_recherche] * 3)
        if self.metier_code:
            parts.append(self.metier_code)
        if self.seniority:
            parts.append(self.seniority.value)
        parts.extend(self.tech_stack[:25])
        parts.extend(self.competences[:25])
        parts.extend(self.langues[:5])
        parts.extend(self.villes[:5])
        if self.raw_text:
            parts.append(self.raw_text[:3500])
        return " ".join(p for p in parts if p)[:4000] or "Job seeker profile"


class CVUploadResponse(BaseModel):
    cv_id: str
    object_key: str
    bucket: str
    status: str = "queued"
    message: str = "CV uploaded; parsing scheduled."
