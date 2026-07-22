"""
Simulateur "et si" : recalculs déterministes à la volée sur des résultats
déjà produits par le pipeline, pour explorer une hypothèse sans relancer
tout le moteur (donc sans nouvel appel LLM, réponse instantanée).

Deux leviers, choisis parce qu'ils répondent directement à l'arbitrage
RTO/RPO sous incertitude demandé par le brief, sans rien inventer :
- le coût de l'attente (combien perdre coûte chaque heure de plus avant
  d'agir), rejoué avec la même formule que tools/risk_calc.py ;
- le coût d'une panne en cascade (si un actif supplémentaire tombe,
  quels systèmes restent bloqués), lu directement dans le graphe déjà
  construit via la convention "A -> B = A dépend de B".
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from core.schemas import RebuildStep, RiskItem


@dataclass
class DelaySimulation:
    extra_hours: float
    items: list[RiskItem]
    total_before_eur: float
    total_after_eur: float
    eur_per_extra_hour: float

    @property
    def delta_eur(self) -> float:
        return self.total_after_eur - self.total_before_eur


def simulate_extra_delay(risk_items: list[RiskItem], extra_hours: float) -> DelaySimulation:
    """Et si on attend `extra_hours` de plus avant d'agir ? Recalcule la
    perte financière de chaque actif exposé (l'écart en heures augmente
    d'autant, le coût horaire du BIA ne change pas) - même formule que
    tools/risk_calc.py, juste rejouée avec un écart hypothétique plus
    grand. Aucune nouvelle donnée n'est inventée : seule l'hypothèse de
    temps change."""
    before = [it for it in risk_items if it.data_sufficient]
    total_before = sum(it.estimated_loss_eur for it in before)
    eur_per_hour_sum = sum(it.eur_per_hour or 0.0 for it in before)

    updated: list[RiskItem] = []
    for it in risk_items:
        if not it.data_sufficient or it.gap_hours is None or it.eur_per_hour is None:
            updated.append(it)
            continue
        new_gap = it.gap_hours + extra_hours
        updated.append(it.model_copy(update={
            "gap_hours": new_gap,
            "estimated_loss_eur": new_gap * it.eur_per_hour,
        }))
    total_after = sum(it.estimated_loss_eur for it in updated if it.data_sufficient)

    return DelaySimulation(
        extra_hours=extra_hours, items=updated,
        total_before_eur=total_before, total_after_eur=total_after,
        eur_per_extra_hour=eur_per_hour_sum,
    )


@dataclass
class FailureSimulation:
    node: str
    step_number: int | None
    already_at_risk: bool
    newly_blocked: list[str] = field(default_factory=list)
    newly_blocked_previously_safe: list[str] = field(default_factory=list)


def simulate_extra_failure(graph: nx.DiGraph, steps: list[RebuildStep], node: str) -> FailureSimulation:
    """Et si `node` tombe aussi en panne ? Les ancêtres de `node` dans le
    graphe de dépendances sont, par construction (A -> B = "A dépend de
    B"), exactement les systèmes qui ne pourront pas redémarrer tant que
    `node` n'est pas traité - une lecture directe du graphe déjà
    construit, pas une nouvelle hypothèse sur les données."""
    step_by_node = {s.node: s for s in steps}
    current = step_by_node.get(node)
    already_at_risk = bool(current and current.status_kind in ("COMPROMIS", "RESTAURATION_RISQUEE"))

    newly_blocked = sorted(nx.ancestors(graph, node)) if node in graph else []
    previously_safe = sorted(
        n for n in newly_blocked
        if step_by_node.get(n) and step_by_node[n].status_kind == "FIABLE"
    )

    return FailureSimulation(
        node=node, step_number=current.step if current else None,
        already_at_risk=already_at_risk,
        newly_blocked=newly_blocked,
        newly_blocked_previously_safe=previously_safe,
    )
