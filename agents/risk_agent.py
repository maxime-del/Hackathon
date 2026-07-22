"""
Spécialiste "risque financier" : appelle le calcul déterministe (écart RPO
x coût horaire du BIA, généralisé à tous les actifs), puis demande à Qwen
une explication courte du pourquoi - jamais un recalcul.
"""
from pathlib import Path

from core.format import eur
from core.llm import call_llm
from core.schemas import RiskItem
from core.state import EngineState
from tools.risk_calc import compute_exposures

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "risk.md").read_text()


def run(state: EngineState) -> EngineState:
    exposures = compute_exposures(state.process_id)

    if not exposures[0].data_sufficient:
        exp = exposures[0]
        item = RiskItem(
            asset=exp.asset, process_id=exp.process_id, description=exp.confidence_note,
            estimated_loss_eur=0.0, confidence_note=exp.confidence_note, sources=[],
            data_sufficient=False,
        )
        state.risk_items = [item]
        state.risk_narrative = exp.confidence_note
        return state

    items = [
        RiskItem(
            asset=exp.asset, process_id=exp.process_id,
            description=(
                f"Écart entre le RPO cible ({exp.rpo_target}) et la dernière sauvegarde fiable "
                f"({exp.last_reliable_backup}), soit {exp.gap_hours:.1f}h exposées."
            ),
            rpo_target=exp.rpo_target, last_reliable_backup=exp.last_reliable_backup.to_pydatetime(),
            gap_hours=exp.gap_hours, eur_per_hour=exp.eur_per_hour,
            estimated_loss_eur=exp.estimated_loss_eur, confidence_note=exp.confidence_note,
            sources=exp.sources,
        )
        for exp in exposures
    ]
    state.risk_items = items

    top = items[0]
    others = items[1:]
    context = (
        f"Actif le plus exposé : {top.asset}. RPO cible : {top.rpo_target}. Dernière sauvegarde fiable : "
        f"{top.last_reliable_backup}. Écart : {top.gap_hours:.1f}h. Coût : {eur(top.eur_per_hour)}/h. "
        f"Perte estimée : {eur(top.estimated_loss_eur)}. Note : {top.confidence_note} "
        f"(sources : {', '.join(top.sources)}).\n"
        + ("Autres actifs également en violation de RPO : " + ", ".join(
            f"{it.asset} ({eur(it.estimated_loss_eur)})" for it in others
        ) if others else "Aucun autre actif en violation de RPO.")
    )
    fallback = (
        f"L'actif le plus exposé est {top.asset} : la dernière sauvegarde fiable date d'avant l'incident de "
        f"{top.gap_hours:.1f} heures, ce qui représente environ {eur(top.estimated_loss_eur)} de données "
        f"exposées. {top.confidence_note}"
    )
    state.risk_narrative = call_llm(PROMPT, context, "Explique ce risque en 2-3 phrases.", fallback)
    return state
