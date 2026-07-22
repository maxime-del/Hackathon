"""
Schémas partagés entre agents. Toute affirmation produite par un agent doit
porter une source et un niveau de confiance - c'est la règle non négociable
qui empêche le système de "halluciner" un fait sans provenance.
"""
from datetime import datetime
from pydantic import BaseModel, Field

Confidence = str  # "SUR" | "INCERTAIN" | "DANGER" | "INCONNU"
Severity = str  # "CRITIQUE" | "HAUTE" | "MOYENNE"


class Finding(BaseModel):
    """Une incohérence ou un fait notable détecté dans le corpus."""
    id: str
    severity: Severity
    title_tech: str
    title_human: str
    detail_tech: str
    detail_human: str
    sources: list[str] = Field(default_factory=list)
    action_pro: str | None = None
    asset: str | None = None  # noeud du graphe concerné, pour rattacher ce constat à une étape du plan


class RebuildStep(BaseModel):
    """Une étape du plan de reconstruction, avec sa justification sourcée."""
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
    # Pourquoi le statut est rouge, precisement (voir tools/graph_builder.py
    # STATUS_KIND_RANK) : COMPROMIS (l'actif est declare atteint, hors
    # service) vs RESTAURATION_RISQUEE (l'actif n'est pas forcement atteint,
    # mais la donnee pour le restaurer n'est pas fiable) vs A_VERIFIER /
    # NON_DOCUMENTE / FIABLE. Distinct du risk_level ci-dessous : status_kind
    # dit CE QUI ne va pas, risk_level dit A QUEL POINT c'est risque d'agir.
    status_kind: str = "FIABLE"
    # Facteur de risque de la décision "redémarrer maintenant", calculé par le
    # décideur à partir de la confiance du noeud + des anomalies liées + de
    # l'impact financier - jamais deviné par le LLM.
    risk_level: str = "FAIBLE"  # FAIBLE | MOYEN | ELEVE
    risk_consequence: str = ""
    linked_findings: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    """Un risque financier ou opérationnel chiffré et sourcé."""
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
    """Un extrait retrouvé par le RAG, toujours avec sa source et son score."""
    text: str
    source: str
    score: float
