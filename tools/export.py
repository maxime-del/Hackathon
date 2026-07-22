"""
Export deterministe du plan de reprise en Markdown. Pur formatage a partir
de l'EngineState deja calcule - aucun recalcul, aucun appel LLM.
"""
from core.format import eur
from core.state import EngineState
from tools.narrate import human_name


def build_export_markdown(state: EngineState) -> str:
    risk = state.risk_items[0] if state.risk_items else None
    lines = [
        f"# Plan de redemarrage — Processus {state.process_id}",
        "",
        "## Risque financier principal",
    ]
    if risk:
        lines.append(
            f"Actif le plus expose : {risk.asset} — Perte estimee : {eur(risk.estimated_loss_eur)} "
            f"(source : {', '.join(risk.sources)})"
        )
    lines += ["", "## A faire valider par un professionnel"]
    for f in state.manual_validations:
        lines.append(f"- {f.title_human} : {f.action_pro}")
    lines += ["", "## Plan de redemarrage, dans l'ordre"]
    for s in state.final_plan:
        lines.append(
            f"{s.step}. {human_name(s.node)} — confiance : {s.confidence} — "
            f"{s.risk_level} : {s.risk_consequence}"
        )
    lines += ["", "## Incoherences detectees"]
    for a in state.findings:
        lines.append(f"- [{a.severity}] {a.title_human} (sources : {', '.join(a.sources)})")
    return "\n".join(lines)
