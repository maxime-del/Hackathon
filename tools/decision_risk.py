"""
Facteur de risque par décision de reconstruction : pour chaque étape du
plan, quantifie ce qui peut mal se passer si on redémarre CE système
maintenant, pour qu'un décideur (PDG, cellule de crise) puisse arbitrer
vite sans lire le détail technique.

Déterministe et explicable : le niveau de risque découle de la confiance
déjà calculée sur le noeud (tools/graph_builder.score_node_confidence),
des anomalies déjà détectées qui le concernent (tools/anomaly_checks),
et de l'impact financier déjà chiffré (tools/risk_calc) - rien n'est
inventé ici, ce module ne fait qu'agréger des faits déjà établis.
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
    "DANGER": "Redémarrer ce système sans vérification humaine risque de réintroduire le problème d'origine "
              "(sauvegarde compromise ou manquante).",
    "INCERTAIN": "La sauvegarde disponible n'est pas totalement fiable : redémarrer maintenant peut reposer "
                 "sur une base incomplète ou périmée.",
    "INCONNU": "Aucune information fiable sur cet élément : le redémarrer sans vérification préalable est un pari.",
    "SUR": "Risque limité : sauvegarde fiable et documentée.",
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
            parts.append(f"Impact chiffré si la donnée est fausse ou perdue : {eur(exposure.estimated_loss_eur)}.")
            if RISK_ORDER["ELEVE"] > RISK_ORDER[level]:
                level = "ELEVE"

        if len(step.dependents) >= 3:
            parts.append(
                f"Attention si vous retardez cette étape : {len(step.dependents)} autres systèmes en dépendent "
                f"et resteront bloqués."
            )

        updated.append(step.model_copy(update={
            "risk_level": level,
            "risk_consequence": " ".join(parts),
            "linked_findings": [f.id for f in linked],
        }))
    return updated
