"""
Le decideur: recoit les sorties deja produites par graph_agent,
anomaly_agent et risk_agent, arbitre (quelles anomalies bloquent
reellement une validation humaine) et produit la synthese finale.
Il ne recalcule rien - il combine des resultats deja fiables.
"""
from pathlib import Path

from core.llm import call_llm
from core.state import EngineState
from tools.decision_risk import compute_step_risks

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "decider.md").read_text()


def run(state: EngineState) -> EngineState:
    # Arbitrage: l'ORDRE du plan reste celui du graph_agent (deja fiable et
    # reproductible) ; le decideur y ajoute le facteur de risque par etape
    # (confiance + anomalies liees + impact financier) et extrait les
    # points qui exigent une validation humaine avant d'agir.
    state.final_plan = compute_step_risks(state.restore_steps, state.findings, state.risk_items)
    state.manual_validations = [f for f in state.findings if f.action_pro]

    context = (
        f"[Graphe] {state.graph_narrative}\n\n"
        f"[Anomalies] {state.anomaly_narrative}\n\n"
        f"[Risque] {state.risk_narrative}\n\n"
        f"Nombre d'etapes de validation humaine requises: {len(state.manual_validations)}."
    )
    top_blocker = state.manual_validations[0].title_tech if state.manual_validations else "aucun point de blocage critique identifie"
    fallback = (
        f"Point de blocage principal : {top_blocker}. {state.risk_narrative} "
        f"{len(state.manual_validations)} decision(s) doivent etre validees par un professionnel avant "
        f"toute action de restauration."
    )
    state.decider_narrative = call_llm(
        PROMPT, context,
        "Redige la synthese finale pour la cellule de crise (5-6 phrases).", fallback,
    )
    return state
