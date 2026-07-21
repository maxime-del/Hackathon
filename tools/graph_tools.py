"""
Interface "outils" du graphe, pensee pour etre appelee par le graph_agent:
trois fonctions a la granularite d'un tool-call, toutes deterministes et
reutilisant graph_builder/restore_plan sans dupliquer la logique.
"""
import networkx as nx

from tools.graph_builder import build_dependency_graph
from tools.restore_plan import RestoreStep, compute_restore_plan


def topological_order(process_id: str = "P01") -> tuple[nx.DiGraph, list[RestoreStep], list[tuple[str, str]]]:
    """Construit le graphe et renvoie l'ordre de reconstruction complet."""
    graph = build_dependency_graph(process_id)
    steps, broken_cycles = compute_restore_plan(graph, process_id)
    return graph, steps, broken_cycles


def critical_paths(graph: nx.DiGraph, steps: list[RestoreStep], process_id: str = "P01") -> list[str]:
    """Le chemin le plus long (le plus de prerequis en cascade) jusqu'a P01 -
    c'est la chaine qui determine la duree totale de reconstruction."""
    if not steps:
        return []
    depth_by_node = {s.node: s.depth for s in steps}
    end_node = max(depth_by_node, key=depth_by_node.get)
    path = [end_node]
    current = end_node
    while True:
        succs = list(graph.successors(current))
        if not succs:
            break
        current = max(succs, key=lambda n: depth_by_node.get(n, -1))
        path.append(current)
    return path


def blockers(steps: list[RestoreStep]) -> list[RestoreStep]:
    """Noeuds a la fois bloquants (le reste ne peut pas redemarrer sans eux)
    et a risque (confiance DANGER/INCONNU) - les vrais points de blocage."""
    return [s for s in steps if s.criticality == "Bloquante" and s.confidence in ("DANGER", "INCONNU")]
