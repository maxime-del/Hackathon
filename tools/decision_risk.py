"""
Facteur de risque par decision de reconstruction: pour chaque etape du
plan, quantifie ce qui peut mal se passer si on redemarre CE systeme
maintenant, pour qu'un decideur (PDG, cellule de crise) puisse arbitrer
vite sans lire le detail technique.

Deterministe et explicable: le niveau de risque decoule de la confiance
deja calculee sur le noeud (tools/graph_builder.score_node_confidence),
des anomalies deja detectees qui le concernent (tools/anomaly_checks),
et de l'impact financier deja chiffre (tools/risk_calc) - rien n'est
invente ici, ce module ne fait qu'agreger des faits deja etablis.
"""
from collections import defaultdict

from core.format import eur
from core.schemas import Finding, RebuildStep, RiskItem

RISK_ORDER = {"FAIBLE": 0, "MOYEN": 1, "ELEVE": 2}

_BASE_LEVEL_BY_CONFIDENCE = {
    "DANGER": "ELEVE",
    "INCERTAIN": "MOYEN",
    "INCONNU": "MOYEN",
    "SUR": "FAIBLE",
}

_LEVEL_BY_SEVERITY = {"CRITIQUE": "ELEVE", "HAUTE": "MOYEN", "MOYENNE": "FAIBLE"}

_BASE_CONSEQUENCE_BY_CONFIDENCE = {
    "DANGER": "Redemarrer ce systeme sans verification humaine risque de reintroduire le probleme d'origine "
              "(sauvegarde compromise ou manquante).",
    "INCERTAIN": "La sauvegarde disponible n'est pas totalement fiable : redemarrer maintenant peut reposer "
                 "sur une base incomplete ou perimee.",
    "INCONNU": "Aucune information fiable sur cet element : le redemarrer sans verification prealable est un pari.",
    "SUR": "Risque limite : sauvegarde fiable et documentee.",
}


def compute_step_risks(
    steps: list[RebuildStep], findings: list[Finding], risk_items: list[RiskItem],
) -> list[RebuildStep]:
    findings_by_asset: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.asset:
            findings_by_asset[f.asset].append(f)

    risk_by_asset = {r.asset: r for r in risk_items if r.data_sufficient}

    updated: list[RebuildStep] = []
    for step in steps:
        linked = findings_by_asset.get(step.node, [])
        level = _BASE_LEVEL_BY_CONFIDENCE.get(step.confidence, "MOYEN")
        for f in linked:
            candidate = _LEVEL_BY_SEVERITY.get(f.severity, "FAIBLE")
            if RISK_ORDER[candidate] > RISK_ORDER[level]:
                level = candidate

        parts = [_BASE_CONSEQUENCE_BY_CONFIDENCE.get(step.confidence, "Confiance non evaluee.")]
        for f in linked:
            parts.append(f.title_human)

        exposure = risk_by_asset.get(step.node)
        if exposure:
            parts.append(f"Impact chiffre si la donnee est fausse ou perdue : {eur(exposure.estimated_loss_eur)}.")
            if RISK_ORDER["ELEVE"] > RISK_ORDER[level]:
                level = "ELEVE"

        if len(step.dependents) >= 3:
            parts.append(
                f"Attention si vous retardez cette etape : {len(step.dependents)} autres systemes en dependent "
                f"et resteront bloques."
            )

        updated.append(step.model_copy(update={
            "risk_level": level,
            "risk_consequence": " ".join(parts),
            "linked_findings": [f.id for f in linked],
        }))
    return updated
