"""
Spécialiste "traduction" : seul agent qui s'adresse directement au gérant.
Ne reçoit jamais les CSV bruts - uniquement le plan final et les
constats déjà arbitrés par le décideur. Fabrique aussi la réponse aux
questions libres posées dans l'app, avec le même contrat de sourcing.
"""
from pathlib import Path

from core.format import eur
from core.llm import call_llm
from core.state import EngineState

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "translator.md").read_text()


def build_context(state: EngineState) -> str:
    risk = state.risk_items[0] if state.risk_items else None
    lines = [f"Processus étudié : {state.process_id} (gestion des commandes e-commerce)."]
    if risk and risk.data_sufficient:
        lines.append(
            f"Perte financière estimée : {eur(risk.estimated_loss_eur)} "
            f"(écart de {risk.gap_hours:.1f}h x {eur(risk.eur_per_hour)}/h, "
            f"sources : {', '.join(risk.sources)})."
        )
    elif risk:
        lines.append(f"Risque financier : {risk.confidence_note}")
    lines.append("Synthèse du décideur : " + state.decider_narrative)
    lines.append("À faire valider par un professionnel avant d'agir :")
    for f in state.manual_validations:
        lines.append(f"- {f.title_tech} : {f.action_pro} (sources : {', '.join(f.sources)})")
    lines.append("Ordre de reconstruction (premières étapes) :")
    for s in state.final_plan[:12]:
        lines.append(f"  {s.step}. {s.node} (catégorie {s.category}, confiance {s.confidence})")
    return "\n".join(lines)


def run(state: EngineState) -> EngineState:
    context = build_context(state)
    risk = state.risk_items[0] if state.risk_items else None
    fallback = (
        "Votre boutique en ligne est bloquée car plusieurs briques essentielles sont touchées. "
        + (f"Une partie des commandes récentes (environ {risk.gap_hours:.0f} heures) risque d'être perdue, "
           f"ce qui représente environ {eur(risk.estimated_loss_eur)}. "
           if risk and risk.data_sufficient else "")
        + "Le plan de redémarrage vous donne l'ordre précis pour repartir sans aggraver la situation."
    )
    state.situation_summary = call_llm(
        PROMPT, context,
        "Rédige un court paragraphe (5-6 phrases max) qui explique au gérant, simplement, "
        "pourquoi sa boutique est bloquée, ce qui est le plus urgent, et le risque financier principal.",
        fallback,
    )
    return state


def answer_question(state: EngineState, question: str) -> str:
    context = build_context(state)
    fallback = (
        "Je ne peux pas répondre précisément sans le module de dialogue Qwen actif, mais le plan et les "
        "incohérences ci-dessus contiennent les faits sources pour répondre à cette question."
    )
    return call_llm(
        PROMPT, context,
        f"Le gérant demande : \"{question}\". Réponds uniquement à partir du contexte fourni, en citant "
        f"les sources. Si le contexte ne permet pas de répondre, dis-le clairement.",
        fallback,
    )
