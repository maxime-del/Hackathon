"""
Specialiste "graphe": appelle les tools deterministes (jamais de calcul
fait par le LLM) puis demande a Qwen une explication courte de la chaine
critique, avec repli deterministe si Qwen est indisponible.
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
    )


def run(state: EngineState) -> EngineState:
    graph, steps, broken_cycles = topological_order(state.process_id)
    path = critical_paths(graph, steps, state.process_id)
    blocked = blockers(steps)

    state.graph = graph
    state.restore_steps = [_to_rebuild_step(s) for s in steps]
    state.broken_cycles = broken_cycles

    context = (
        f"Processus: {state.process_id}. {len(steps)} systemes dans le perimetre.\n"
        f"Chaine critique (la plus longue, du prerequis le plus profond au processus): "
        f"{' -> '.join(path)}.\n"
        f"Noeuds a la fois bloquants et a risque (confiance DANGER/INCONNU): "
        + (", ".join(f"{s.node} ({s.confidence})" for s in blocked) if blocked else "aucun") + "."
    )
    fallback = (
        f"La chaine la plus longue de la reconstruction passe par : {' -> '.join(human_name(n) for n in path)}. "
        + (f"Les elements suivants sont a la fois bloquants et a risque : "
           f"{', '.join(human_name(s.node) for s in blocked)}." if blocked
           else "Aucun element bloquant n'est actuellement classe a risque.")
    )
    state.graph_narrative = call_llm(PROMPT, context, "Explique la chaine critique en 3-4 phrases.", fallback)
    return state
