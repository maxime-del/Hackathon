"""
Schemas partages entre agents. Toute affirmation produite par un agent doit
porter une source et un niveau de confiance - c'est la regle non negociable
qui empeche le systeme de "halluciner" un fait sans provenance.
"""
from datetime import datetime
from pydantic import BaseModel, Field

Confidence = str  # "SUR" | "INCERTAIN" | "DANGER" | "INCONNU"
Severity = str  # "CRITIQUE" | "HAUTE" | "MOYENNE"


class Finding(BaseModel):
    """Une incoherence ou un fait notable detecte dans le corpus."""
    id: str
    severity: Severity
    title_tech: str
    title_human: str
    detail_tech: str
    detail_human: str
    sources: list[str] = Field(default_factory=list)
    action_pro: str | None = None


class RebuildStep(BaseModel):
    """Une etape du plan de reconstruction, avec sa justification sourcee."""
    step: int
    node: str
    category: str
    depth: int
    criticality: str
    confidence: Confidence
    confidence_reasons: list[str] = Field(default_factory=list)
    confidence_sources: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    """Un risque financier ou operationnel chiffre et sourcee."""
    asset: str
    process_id: str
    description: str
    rpo_target: str | None = None
    last_reliable_backup: datetime | None = None
    gap_hours: float | None = None
    eur_per_hour: float | None = None
    estimated_loss_eur: float
    confidence_note: str
    sources: list[str] = Field(default_factory=list)
    data_sufficient: bool = True


class RetrievedPassage(BaseModel):
    """Un extrait retrouve par le RAG, toujours avec sa source et son score."""
    text: str
    source: str
    score: float
