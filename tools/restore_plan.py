"""
Calcul de l'ordre de reconstruction : tri topologique du graphe de
dépendances, pondéré par criticité et confiance des sauvegardes.

Rien n'est deviné : le code calcule un ordre reproductible, l'IA se
contentera plus tard de le mettre en phrases.
"""
from dataclasses import dataclass, field
import networkx as nx

CRITICALITY_RANK = {
    "Blocker": 0, "Bloquante": 0, "Bloquante si paiement CB": 0,
    "Critical": 0, "Critique": 0,
    "Important": 1, "Importante": 1, "High": 1, "Haute": 1,
    "Degraded": 2, "Degrade mais important": 2, "Medium": 2, "Moyenne": 2,
    "Low": 3,
}
CONFIDENCE_RANK = {"SUR": 0, "INCERTAIN": 1, "DANGER": 2, "INCONNU": 3}


@dataclass
class RestoreStep:
    step: int
    node: str
    category: str
    depth: int
    criticality: str
    confidence: str
    confidence_reasons: list[str]
    confidence_sources: list[str]
    prerequisites: list[str]
    dependents: list[str] = field(default_factory=list)
    edges_in: list[dict] = field(default_factory=list)
    status_kind: str = "FIABLE"


def _break_cycles(G: nx.DiGraph) -> list[tuple[str, str]]:
    """Supprime les cycles en coupant l'arete de plus faible criticite du
    cycle. Retourne la liste des aretes supprimees (a signaler comme anomalie).
    """
    removed = []
    while True:
        try:
            cycle = nx.find_cycle(G)
        except nx.NetworkXNoCycle:
            break
        weakest = max(
            cycle,
            key=lambda e: CRITICALITY_RANK.get(G.edges[e[0], e[1]].get("criticality"), 9),
        )
        G.remove_edge(*weakest)
        removed.append(weakest)
    return removed


def compute_restore_plan(G: nx.DiGraph, process_id: str = "P01") -> tuple[list[RestoreStep], list[tuple[str, str]]]:
    work = G.copy()
    broken_cycles = _break_cycles(work)

    # depth[n] = nombre de sauts jusqu'au prerequis le plus profond
    # (0 = feuille, ne depend plus de rien dans le sous-graphe).
    topo = list(nx.topological_sort(work))  # ordre "consommateur avant fourni"
    depth: dict[str, int] = {}
    for n in reversed(topo):  # on traite les feuilles (pas de successeurs) d'abord
        succs = list(work.successors(n))
        depth[n] = 0 if not succs else 1 + max(depth[s] for s in succs)

    nodes = [n for n in work.nodes if n != process_id]

    def sort_key(n):
        crit = min(
            (CRITICALITY_RANK.get(work.edges[n, s].get("criticality"), 9) for s in work.successors(n)),
            default=CRITICALITY_RANK.get(work.nodes[n].get("cmdb_criticality"), 2),
        )
        conf = CONFIDENCE_RANK.get(work.nodes[n].get("confidence", "INCONNU"), 3)
        return (depth[n], crit, conf, n)

    ordered = sorted(nodes, key=sort_key)

    steps: list[RestoreStep] = []
    for i, n in enumerate(ordered, start=1):
        data = work.nodes[n]
        prereqs = list(work.successors(n))
        dependents = list(work.predecessors(n))
        edges_in = [
            {"from": p, **{k: v for k, v in work.edges[n, p].items()}}
            for p in prereqs
        ]
        crit = min(
            (CRITICALITY_RANK.get(work.edges[n, s].get("criticality"), 9) for s in prereqs),
            default=9,
        )
        crit_label = {0: "Bloquante", 1: "Importante", 2: "Moyenne", 3: "Faible"}.get(crit, "Moyenne")
        steps.append(RestoreStep(
            step=i, node=n, category=data.get("category", "Autre"), depth=depth[n],
            criticality=crit_label, confidence=data.get("confidence", "INCONNU"),
            confidence_reasons=data.get("confidence_reasons", []),
            confidence_sources=data.get("confidence_sources", []),
            prerequisites=prereqs, dependents=dependents, edges_in=edges_in,
            status_kind=data.get("status_kind", "FIABLE"),
        ))
    return steps, broken_cycles
