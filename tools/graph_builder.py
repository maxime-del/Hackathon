"""
Construction du graphe de dépendances (NetworkX) pour un processus métier,
et scoring de confiance par noeud.

Convention : une arête A -> B signifie "A dépend de B" (B doit être remis en
service avant A). C'est le sens naturel des CSV source (Application_Dependencies,
Infrastructure_Dependencies, Process_to_Applications_Map).
"""
import networkx as nx
import pandas as pd

from tools.categorize import NodeFacts, build_node_facts, human_category
from tools.data_loader import load_all
from tools.schema_mapping import get_table

CONFIDENCE_RANK = {"SUR": 0, "INCERTAIN": 1, "DANGER": 2, "INCONNU": 3}

# Deux causes tres differentes peuvent mener au meme niveau "DANGER" - le
# statut affiche doit dire LAQUELLE, pas juste "rouge" :
# - COMPROMIS : l'evaluation d'impact officielle declare l'actif compromis
#   (le systeme lui-meme est atteint, hors service tant qu'il n'est pas
#   assaini - le redemarrer tel quel rejoue l'attaque).
# - RESTAURATION_RISQUEE : rien ne dit que l'actif lui-meme est compromis,
#   mais la donnee dont on dispose pour le restaurer (sauvegarde, coffre,
#   vulnerabilite ouverte) n'est pas fiable - le redemarrer est un pari,
#   pas une certitude de rejouer l'attaque.
# Priorite entre causes a niveau DANGER egal : un compromis confirme prime
# toujours sur un simple doute de restauration.
STATUS_KIND_RANK = {"FIABLE": 0, "NON_DOCUMENTE": 1, "A_VERIFIER": 1, "RESTAURATION_RISQUEE": 2, "COMPROMIS": 3}


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
        confidence, reasons, sources, status_kind = score_node_confidence(f)
        sub.nodes[node]["facts"] = f
        sub.nodes[node]["category"] = human_category(node, f.cmdb_type)
        sub.nodes[node]["confidence"] = confidence
        sub.nodes[node]["confidence_reasons"] = reasons
        sub.nodes[node]["confidence_sources"] = sources
        sub.nodes[node]["status_kind"] = status_kind
        sub.nodes[node]["in_cmdb"] = f.in_cmdb

    return sub


def _parse_ts(value) -> pd.Timestamp | None:
    try:
        ts = pd.Timestamp(value)
        return None if pd.isna(ts) else ts
    except (ValueError, TypeError):
        return None


def score_node_confidence(f: NodeFacts) -> tuple[str, list[str], list[str], str]:
    """Retourne (niveau, raisons[], sources[], status_kind) pour un noeud.

    Niveaux, du pire au meilleur : DANGER > INCONNU > INCERTAIN > SUR.
    Règle déterministe : on part de SUR et on dégrade dès qu'un fait
    documenté pose problème (compromission, sauvegarde manquante/violée,
    intégrité non vérifiée, absence de CMDB).

    `status_kind` affine le POURQUOI du niveau affiché à l'écran (voir
    STATUS_KIND_RANK ci-dessus) : un même "DANGER" peut vouloir dire
    "actif compromis, hors service" ou "actif peut-être sain mais la
    donnée pour le restaurer n'est pas fiable" - deux situations bien
    différentes pour un gérant qui doit décider s'il redémarre ou non.
    """
    reasons: list[str] = []
    sources: list[str] = []
    level = "SUR"
    kind = "FIABLE"

    def degrade(new_level: str, reason: str, source: str, new_kind: str):
        nonlocal level, kind
        lvl_rank, cur_rank = CONFIDENCE_RANK[new_level], CONFIDENCE_RANK[level]
        if lvl_rank > cur_rank or (lvl_rank == cur_rank and STATUS_KIND_RANK[new_kind] > STATUS_KIND_RANK[kind]):
            level = new_level
            kind = new_kind
        reasons.append(reason)
        sources.append(source)

    if f.impact_status and "compromis" in str(f.impact_status).lower():
        degrade("DANGER", f"Actif déclaré compromis ({f.impact_status}, confiance {f.impact_confidence})",
                "Impact_Assessment.csv", "COMPROMIS")

    for row in f.vault_rows:
        ts_raw = row.get("Vault_Copy_Timestamp")
        integrity = str(row.get("Integrity_Check", ""))
        if isinstance(ts_raw, str) and ts_raw.strip().lower() == "missing":
            degrade("DANGER", "Aucune copie dans le coffre-fort cyber isolé (Cyber-Vault)",
                    "Cyber_Vault_Catalog.csv", "RESTAURATION_RISQUEE")
        elif integrity.strip().lower() == "not tested":
            degrade("INCERTAIN", "Copie présente dans le coffre-fort mais intégrité jamais testée",
                    "Cyber_Vault_Catalog.csv", "A_VERIFIER")

    for row in f.backup_rows:
        status = str(row.get("RPO_Status", ""))
        notes = str(row.get("Notes", ""))
        if "violation" in status.lower():
            degrade("INCERTAIN", f"Sauvegarde en violation du RPO cible ({row.get('RPO_Target')})",
                    "Backup_Catalog.csv", "A_VERIFIER")
        if any(w in notes.lower() for w in ["contamine", "compromis", "compte admin"]):
            degrade("DANGER", f"Sauvegarde potentiellement compromise : {notes}", "Backup_Catalog.csv",
                    "RESTAURATION_RISQUEE")

    for row in f.vuln_rows:
        if str(row.get("Severity", "")).lower() == "critical":
            degrade("DANGER", f"Vulnérabilité critique ouverte : {row.get('Finding')}",
                    "Vulnerabilities_Extract.csv", "RESTAURATION_RISQUEE")

    if not f.in_cmdb:
        degrade("INCONNU", "Actif absent de la CMDB (non documenté officiellement)", "CMDB_Export.csv",
                "NON_DOCUMENTE")

    if not reasons:
        reasons.append("Aucune anomalie détectée sur cet actif dans le corpus fourni")
        sources.append("CMDB_Export.csv / Backup_Catalog.csv")

    return level, reasons, sources, kind
