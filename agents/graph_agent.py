"""
Spécialiste "graphe" : appelle les tools déterministes (jamais de calcul
fait par le LLM) puis demande à Qwen une explication courte de la chaîne
critique, avec repli déterministe si Qwen est indisponible.
"""
from pathlib import Path

from core.llm import call_llm
from core.schemas import RebuildStep
from core.state import EngineState
from tools.graph_tools import blockers, critical_paths, topological_order
from tools.narrate import human_name

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "graph.md").read_text()


def _to_rebuild_step(step) -> RebuildStep:
    return RebuildStep(
        step=step.step, node=step.node, category=step.category, depth=step.depth,
        criticality=step.criticality, confidence=step.confidence,
        confidence_reasons=step.confidence_reasons, confidence_sources=step.confidence_sources,
        prerequisites=step.prerequisites, dependents=step.dependents,
        status_kind=step.status_kind,
    )


def run(state: EngineState) -> EngineState:
    graph, steps, broken_cycles = topological_order(state.process_id)
    path = critical_paths(graph, steps, state.process_id)
    blocked = blockers(steps)

    state.graph = graph
    state.restore_steps = [_to_rebuild_step(s) for s in steps]
    state.broken_cycles = broken_cycles

    context = (
        f"Processus : {state.process_id}. {len(steps)} systèmes dans le périmètre.\n"
        f"Chaîne critique (la plus longue, du prérequis le plus profond au processus) : "
        f"{' -> '.join(path)}.\n"
        f"Noeuds à la fois bloquants et à risque (confiance DANGER/INCONNU) : "
        + (", ".join(f"{s.node} ({s.confidence})" for s in blocked) if blocked else "aucun") + "."
    )
    fallback = (
        f"La chaîne la plus longue de la reconstruction passe par : {' -> '.join(human_name(n) for n in path)}. "
        + (f"Les éléments suivants sont à la fois bloquants et à risque : "
           f"{', '.join(human_name(s.node) for s in blocked)}." if blocked
           else "Aucun élément bloquant n'est actuellement classé à risque.")
    )
    state.graph_narrative = call_llm(PROMPT, context, "Explique la chaîne critique en 3-4 phrases.", fallback)
    return state
