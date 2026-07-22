"""
Traduit l'EngineState (dataclasses/pydantic + graphe NetworkX) en JSON
serialisable pour le frontend. Aucun calcul metier ici: uniquement de la
mise en forme et des regroupements de presentation (le frontend reste un
pur affichage, comme l'etait la page Streamlit qu'il remplace).
"""
import re

from core.format import eur
from core.state import EngineState
from tools.categorize import LAYER_ORDER
from tools.narrate import human_name, explain_step

_LEADING_EMOJI_RE = re.compile(r"^[^\w(]*")


def _plain_explain(step) -> str:
    """Meme phrase que explain_step, sans l'emoji de tete ni le markdown
    ** ** - le frontend affiche deja sa propre puce de confiance a cote."""
    text = explain_step(step)
    return _LEADING_EMOJI_RE.sub("", text).replace("**", "").strip()

# Slug d'icone envoye au frontend pour chaque categorie technique - le
# frontend choisit son propre pictogramme SVG a partir de ce slug, jamais
# du libelle humain (qui peut varier).
CATEGORY_ICON_SLUGS = {
    "Identité": "identity",
    "Réseau / DNS": "network",
    "Certificats (PKI)": "pki",
    "Coffre-fort secrets": "vault",
    "Sécurité / Supervision": "shield",
    "Sauvegardes": "backup",
    "Serveurs (compute)": "server",
    "Données": "database",
    "Applications": "app",
    "Intégration & messagerie": "link",
    "Autre": "question",
}

RISK_ORDER = {"FAIBLE": 0, "MOYEN": 1, "ELEVE": 2}


def _step_dict(s) -> dict:
    return {
        "step": s.step,
        "node": s.node,
        "human_name": human_name(s.node),
        "explain": _plain_explain(s),
        "category": s.category,
        "depth": s.depth,
        "criticality": s.criticality,
        "confidence": s.confidence,
        "confidence_reasons": s.confidence_reasons,
        "confidence_sources": s.confidence_sources,
        "prerequisites": s.prerequisites,
        "dependents": s.dependents,
        "risk_level": getattr(s, "risk_level", "FAIBLE"),
        "risk_consequence": getattr(s, "risk_consequence", ""),
        "linked_findings": getattr(s, "linked_findings", []),
    }


def _finding_dict(f) -> dict:
    return {
        "id": f.id,
        "severity": f.severity,
        "title_tech": f.title_tech,
        "title_human": f.title_human,
        "detail_tech": f.detail_tech,
        "detail_human": f.detail_human,
        "sources": f.sources,
        "action_pro": f.action_pro,
        "asset": f.asset,
    }


def _risk_dict(r) -> dict:
    return {
        "asset": r.asset,
        "process_id": r.process_id,
        "description": r.description,
        "rpo_target": r.rpo_target,
        "last_reliable_backup": r.last_reliable_backup.isoformat() if r.last_reliable_backup else None,
        "gap_hours": r.gap_hours,
        "eur_per_hour": r.eur_per_hour,
        "estimated_loss_eur": r.estimated_loss_eur,
        "estimated_loss_fmt": eur(r.estimated_loss_eur),
        "confidence_note": r.confidence_note,
        "sources": r.sources,
        "data_sufficient": r.data_sufficient,
    }


def _graph_dict(G) -> dict:
    nodes = [
        {
            "id": n,
            "category": data.get("category", "Autre"),
            "confidence": data.get("confidence", "INCONNU"),
            "kind": data.get("kind", "asset"),
        }
        for n, data in G.nodes(data=True)
    ]
    edges = [
        {
            "source": u,
            "target": v,
            "dependency_type": data.get("dependency_type", ""),
        }
        for u, v, data in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


def _categories(steps: list) -> list[dict]:
    present = sorted(
        {s.category for s in steps},
        key=lambda c: LAYER_ORDER.index(c) if c in LAYER_ORDER else len(LAYER_ORDER),
    )
    out = []
    for cat in present:
        members = [s for s in steps if s.category == cat]
        if any(s.confidence == "DANGER" for s in members):
            status = "DANGER"
        elif any(s.confidence in ("INCERTAIN", "INCONNU") for s in members):
            status = "INCERTAIN"
        else:
            status = "SUR"
        members_sorted = sorted(members, key=lambda s: -RISK_ORDER.get(s.risk_level, 0))
        out.append({
            "key": cat,
            "label": cat,
            "icon": CATEGORY_ICON_SLUGS.get(cat, "question"),
            "count": len(members),
            "status": status,
            "nodes": [
                {
                    "node": s.node,
                    "human_name": human_name(s.node),
                    "risk_level": s.risk_level,
                    "risk_consequence": s.risk_consequence,
                }
                for s in members_sorted
            ],
        })
    return out


def state_to_dict(state: EngineState, llm_available: bool) -> dict:
    steps = state.final_plan
    findings = state.findings
    risk_items = state.risk_items
    primary_risk = risk_items[0] if risk_items else None

    blocking = [s for s in steps if s.criticality == "Bloquante"]
    high_risk = [s for s in steps if s.risk_level == "ELEVE"]
    medium_risk = [s for s in steps if s.risk_level == "MOYEN"]
    low_risk = [s for s in steps if s.risk_level == "FAIBLE"]
    critical_findings = [f for f in findings if f.severity == "CRITIQUE"]

    return {
        "process_id": state.process_id,
        "situation_summary": state.situation_summary,
        "llm_available": llm_available,
        "broken_cycles": [list(c) for c in state.broken_cycles],
        "risk": {
            "primary": _risk_dict(primary_risk) if primary_risk else None,
            "others": [_risk_dict(r) for r in risk_items[1:]],
        },
        "kpis": {
            "steps": len(steps),
            "blocking": len(blocking),
            "high_risk": len(high_risk),
            "medium_risk": len(medium_risk),
            "low_risk": len(low_risk),
            "critical_findings": len(critical_findings),
            "estimated_loss_fmt": eur(primary_risk.estimated_loss_eur) if primary_risk and primary_risk.data_sufficient else "n/a",
        },
        "graph": _graph_dict(state.graph),
        "categories": _categories(steps),
        "steps": [_step_dict(s) for s in steps],
        "findings": [_finding_dict(f) for f in findings],
        "manual_validations": [_finding_dict(f) for f in state.manual_validations],
        "narratives": {
            "graph": state.graph_narrative,
            "anomaly": state.anomaly_narrative,
            "risk": state.risk_narrative,
            "decider": state.decider_narrative,
        },
    }
