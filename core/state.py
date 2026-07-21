"""
Le blackboard partage entre agents: chaque specialiste lit ce dont il a
besoin et ecrit son resultat ici. L'orchestrateur (ingestion_agent) le
construit dans l'ordre; app.py ne fait que le lire pour l'affichage.
"""
from dataclasses import dataclass, field
import networkx as nx

from core.schemas import Finding, RebuildStep, RiskItem


@dataclass
class EngineState:
    process_id: str = "P01"

    # ecrit par graph_agent
    graph: nx.DiGraph | None = None
    restore_steps: list[RebuildStep] = field(default_factory=list)
    broken_cycles: list[tuple] = field(default_factory=list)
    graph_narrative: str = ""

    # ecrit par anomaly_agent
    findings: list[Finding] = field(default_factory=list)
    anomaly_narrative: str = ""

    # ecrit par risk_agent
    risk_items: list[RiskItem] = field(default_factory=list)
    risk_narrative: str = ""

    # ecrit par decider_agent
    final_plan: list[RebuildStep] = field(default_factory=list)
    manual_validations: list[Finding] = field(default_factory=list)
    decider_narrative: str = ""

    # ecrit par translator_agent
    situation_summary: str = ""
