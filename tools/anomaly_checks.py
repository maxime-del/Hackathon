"""
Le seul controle veritablement deterministe qui reste ici : comparer les
dependances DECLAREES par le BIA a celles reellement constatees dans le
graphe. C'est une simple difference d'ensembles sur des donnees deja
chargees - aucun nom d'actif code en dur, ca marche sur n'importe quel
corpus qui a un BIA_Export avec Process_ID/Applications_Declared.

Tout le reste des anomalies (sauvegardes douteuses, contradictions entre
sources, vulnerabilites...) est desormais decouvert par l'anomaly_agent
via une vraie analyse LLM de la fiche de faits (tools/asset_facts.py) -
voir agents/anomaly_agent.py. On perd le cote 100% deterministe sur cette
partie, mais on gagne la capacite a fonctionner sur des donnees qu'on n'a
jamais vues.
"""
from dataclasses import dataclass, field

import pandas as pd

from tools.data_loader import load_all
from tools.schema_mapping import get_table


@dataclass
class Anomaly:
    id: str
    severity: str  # CRITIQUE / HAUTE / MOYENNE
    title_tech: str
    title_human: str
    detail_tech: str
    detail_human: str
    sources: list[str] = field(default_factory=list)
    action_pro: str | None = None
    asset: str | None = None


def _bia_row(bia: pd.DataFrame, process_id: str) -> pd.Series | None:
    matches = bia[bia["Process_ID"] == process_id] if "Process_ID" in bia.columns else bia.iloc[0:0]
    return matches.iloc[0] if not matches.empty else None


def _bia_declared_apps(bia_row: pd.Series) -> set[str]:
    declared = bia_row.get("Applications_Declared")
    if declared is None or (isinstance(declared, float) and pd.isna(declared)):
        return set()
    return {a.strip() for a in str(declared).split(";") if a.strip()}


def bia_gap_finding(process_id: str, graph_nodes: set[str]) -> Anomaly | None:
    tables = load_all()
    bia = get_table(tables, "BIA_Export")
    bia_row = _bia_row(bia, process_id)
    if bia_row is None:
        return None

    declared = _bia_declared_apps(bia_row)
    missing = sorted((graph_nodes - declared) - {process_id})
    if not missing:
        return None

    return Anomaly(
        id="BIA_INCOMPLETE",
        severity="CRITIQUE",
        title_tech=f"Le BIA de {process_id} omet {len(missing)} dependances constatees dans le graphe",
        title_human="La fiche officielle de risque ne liste pas tous les systemes reellement utilises",
        detail_tech=(
            f"BIA_Export.csv declare seulement : {', '.join(sorted(declared)) or '(rien)'}. "
            f"Le graphe de dependances reel montre que {process_id} depend aussi de : {', '.join(missing)}."
        ),
        detail_human=(
            "Le document officiel de risque ne liste pas tous les systemes dont depend reellement ce "
            "processus — si personne ne le sait, on les oublie a la reconstruction."
        ),
        sources=["BIA_Export.csv", "Application_Dependencies.csv", "Process_to_Applications_Map.csv"],
        asset=None,
    )
