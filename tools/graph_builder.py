"""
Construction du graphe de dependances (NetworkX) pour un processus metier,
et scoring de confiance par noeud.

Convention: une arete A -> B signifie "A depend de B" (B doit etre remis en
service avant A). C'est le sens naturel des CSV source (Application_Dependencies,
Infrastructure_Dependencies, Process_to_Applications_Map).
"""
import networkx as nx
import pandas as pd

from tools.categorize import NodeFacts, build_node_facts, human_category
from tools.data_loader import load_all
from tools.schema_mapping import get_table

CONFIDENCE_RANK = {"SUR": 0, "INCERTAIN": 1, "DANGER": 2, "INCONNU": 3}


def build_dependency_graph(process_id: str = "P01") -> nx.DiGraph:
    tables = load_all()
    process_apps = get_table(tables, "Process_to_Applications_Map")
    app_deps = get_table(tables, "Application_Dependencies")
    infra_deps = get_table(tables, "Infrastructure_Dependencies")

    G = nx.DiGraph()
    G.add_node(process_id, kind="process")

    if "Process_ID" in process_apps.columns:
        for _, row in process_apps[process_apps["Process_ID"] == process_id].iterrows():
            G.add_edge(
                process_id, row.get("Application"),
                dependency_type=row.get("Role", ""), criticality=row.get("Dependency_Level", "Moyenne"),
                source_doc="Process_to_Applications_Map.csv", confidence="High",
                notes=row.get("Source", ""),
            )

    for _, row in app_deps.iterrows():
        src = str(row.get("Source", "")).replace("P01 Gestion commandes", process_id)
        target = row.get("Target")
        if not src or target is None or (isinstance(target, float) and pd.isna(target)):
            continue
        G.add_edge(
            src, target,
            dependency_type=row.get("Dependency_Type", ""), criticality=row.get("Criticality", "Moyenne"),
            source_doc=f"Application_Dependencies.csv ({row.get('Source_Document', 'inconnue')})",
            confidence=row.get("Confidence", "Medium"), notes=row.get("Notes", ""),
        )

    for _, row in infra_deps.iterrows():
        asset, depends_on = row.get("Asset"), row.get("Depends_On")
        if pd.isna(asset) or pd.isna(depends_on):
            continue
        G.add_edge(
            asset, depends_on,
            dependency_type=row.get("Reason", ""), criticality=row.get("Criticality", "Moyenne"),
            source_doc="Infrastructure_Dependencies.csv", confidence="High",
            notes=row.get("Notes", ""),
        )

    # Ne garder que le sous-graphe pertinent pour le processus (P01 + tout
    # ce qui est atteignable en descendant les dependances).
    reachable = {process_id} | nx.descendants(G, process_id)
    sub = G.subgraph(reachable).copy()

    facts = build_node_facts(tables)
    for node in sub.nodes:
        f = facts.get(node, NodeFacts(node=node))
        confidence, reasons, sources = score_node_confidence(f)
        sub.nodes[node]["facts"] = f
        sub.nodes[node]["category"] = human_category(node, f.cmdb_type)
        sub.nodes[node]["confidence"] = confidence
        sub.nodes[node]["confidence_reasons"] = reasons
        sub.nodes[node]["confidence_sources"] = sources
        sub.nodes[node]["in_cmdb"] = f.in_cmdb

    return sub


def _parse_ts(value) -> pd.Timestamp | None:
    try:
        ts = pd.Timestamp(value)
        return None if pd.isna(ts) else ts
    except (ValueError, TypeError):
        return None


def score_node_confidence(f: NodeFacts) -> tuple[str, list[str], list[str]]:
    """Retourne (niveau, raisons[], sources[]) pour un noeud.

    Niveaux, du pire au meilleur: DANGER > INCONNU > INCERTAIN > SUR.
    Regle deterministe: on part de SUR et on degrade des qu'un fait
    documente pose probleme (compromission, sauvegarde manquante/violee,
    integrite non verifiee, absence de CMDB).
    """
    reasons: list[str] = []
    sources: list[str] = []
    level = "SUR"

    def degrade(new_level: str, reason: str, source: str):
        nonlocal level
        if CONFIDENCE_RANK[new_level] > CONFIDENCE_RANK[level]:
            level = new_level
        reasons.append(reason)
        sources.append(source)

    if f.impact_status and "compromis" in str(f.impact_status).lower():
        degrade("DANGER", f"Actif declare compromis ({f.impact_status}, confiance {f.impact_confidence})",
                "Impact_Assessment.csv")

    for row in f.vault_rows:
        ts_raw = row.get("Vault_Copy_Timestamp")
        integrity = str(row.get("Integrity_Check", ""))
        if isinstance(ts_raw, str) and ts_raw.strip().lower() == "missing":
            degrade("DANGER", "Aucune copie dans le coffre-fort cyber isole (Cyber-Vault)",
                    "Cyber_Vault_Catalog.csv")
        elif integrity.strip().lower() == "not tested":
            degrade("INCERTAIN", "Copie presente dans le coffre-fort mais integrite jamais testee",
                    "Cyber_Vault_Catalog.csv")

    for row in f.backup_rows:
        status = str(row.get("RPO_Status", ""))
        notes = str(row.get("Notes", ""))
        if "violation" in status.lower():
            degrade("INCERTAIN", f"Sauvegarde en violation du RPO cible ({row.get('RPO_Target')})",
                    "Backup_Catalog.csv")
        if any(w in notes.lower() for w in ["contamine", "compromis", "compte admin"]):
            degrade("DANGER", f"Sauvegarde potentiellement compromise: {notes}", "Backup_Catalog.csv")

    for row in f.vuln_rows:
        if str(row.get("Severity", "")).lower() == "critical":
            degrade("DANGER", f"Vulnerabilite critique ouverte: {row.get('Finding')}",
                    "Vulnerabilities_Extract.csv")

    if not f.in_cmdb:
        degrade("INCONNU", "Actif absent de la CMDB (non documente officiellement)", "CMDB_Export.csv")

    if not reasons:
        reasons.append("Aucune anomalie detectee sur cet actif dans le corpus fourni")
        sources.append("CMDB_Export.csv / Backup_Catalog.csv")

    return level, reasons, sources
