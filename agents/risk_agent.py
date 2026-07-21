"""
Specialiste "risque financier": appelle le calcul deterministe (ecart RPO
x cout horaire du BIA), puis demande a Qwen une explication courte du
pourquoi - jamais un recalcul.
"""
from pathlib import Path

from core.format import eur
from core.llm import call_llm
from core.schemas import RiskItem
from core.state import EngineState
from tools.risk_calc import euro_impact

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "risk.md").read_text()


def run(state: EngineState) -> EngineState:
    exposure = euro_impact(state.process_id)

    if not exposure.data_sufficient:
        item = RiskItem(
            asset=exposure.asset, process_id=exposure.process_id,
            description=exposure.confidence_note,
            estimated_loss_eur=0.0, confidence_note=exposure.confidence_note, sources=[],
            data_sufficient=False,
        )
        state.risk_items = [item]
        state.risk_narrative = exposure.confidence_note
        return state

    item = RiskItem(
        asset=exposure.asset, process_id=exposure.process_id,
        description=(
            f"Ecart entre le RPO cible ({exposure.rpo_target}) et la derniere sauvegarde fiable "
            f"({exposure.last_reliable_backup}), soit {exposure.gap_hours:.1f}h de commandes exposees."
        ),
        rpo_target=exposure.rpo_target,
        last_reliable_backup=exposure.last_reliable_backup.to_pydatetime(),
        gap_hours=exposure.gap_hours, eur_per_hour=exposure.eur_per_hour,
        estimated_loss_eur=exposure.estimated_loss_eur, confidence_note=exposure.confidence_note,
        sources=exposure.sources,
    )
    state.risk_items = [item]

    context = (
        f"Actif: {item.asset}. RPO cible: {item.rpo_target}. Derniere sauvegarde fiable: "
        f"{item.last_reliable_backup}. Ecart: {item.gap_hours:.1f}h. Cout: {eur(item.eur_per_hour)}/h. "
        f"Perte estimee: {eur(item.estimated_loss_eur)}. Note: {item.confidence_note} "
        f"(sources: {', '.join(item.sources)})."
    )
    fallback = (
        f"La derniere sauvegarde fiable des commandes date d'avant l'incident de {item.gap_hours:.1f} heures, "
        f"ce qui represente environ {eur(item.estimated_loss_eur)} de commandes exposees. {item.confidence_note}"
    )
    state.risk_narrative = call_llm(PROMPT, context, "Explique ce risque en 2-3 phrases.", fallback)
    return state
