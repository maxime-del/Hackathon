"""
Specialiste "traduction": seul agent qui s'adresse directement au gerant.
Ne recoit jamais les CSV bruts - uniquement le plan final et les
constats deja arbitres par le decideur. Fabrique aussi la reponse aux
questions libres posees dans l'app, avec le meme contrat de sourcing.
"""
from pathlib import Path

from core.format import eur
from core.llm import call_llm
from core.state import EngineState

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "translator.md").read_text()


def build_context(state: EngineState) -> str:
    risk = state.risk_items[0] if state.risk_items else None
    lines = [f"Processus etudie: {state.process_id} (gestion des commandes e-commerce)."]
    if risk and risk.data_sufficient:
        lines.append(
            f"Perte financiere estimee: {eur(risk.estimated_loss_eur)} "
            f"(ecart de {risk.gap_hours:.1f}h x {eur(risk.eur_per_hour)}/h, "
            f"sources: {', '.join(risk.sources)})."
        )
    elif risk:
        lines.append(f"Risque financier: {risk.confidence_note}")
    lines.append("Synthese du decideur: " + state.decider_narrative)
    lines.append("A faire valider par un professionnel avant d'agir:")
    for f in state.manual_validations:
        lines.append(f"- {f.title_tech}: {f.action_pro} (sources: {', '.join(f.sources)})")
    lines.append("Ordre de reconstruction (premieres etapes):")
    for s in state.final_plan[:12]:
        lines.append(f"  {s.step}. {s.node} (categorie {s.category}, confiance {s.confidence})")
    return "\n".join(lines)


def run(state: EngineState) -> EngineState:
    context = build_context(state)
    risk = state.risk_items[0] if state.risk_items else None
    fallback = (
        "Votre boutique en ligne est bloquee car plusieurs briques essentielles sont touchees. "
        + (f"Une partie des commandes recentes (environ {risk.gap_hours:.0f} heures) risque d'etre perdue, "
           f"ce qui represente environ {eur(risk.estimated_loss_eur)}. "
           if risk and risk.data_sufficient else "")
        + "Le plan de redemarrage vous donne l'ordre precis pour repartir sans aggraver la situation."
    )
    state.situation_summary = call_llm(
        PROMPT, context,
        "Redige un court paragraphe (5-6 phrases max) qui explique au gerant, simplement, "
        "pourquoi sa boutique est bloquee, ce qui est le plus urgent, et le risque financier principal.",
        fallback,
    )
    return state


def answer_question(state: EngineState, question: str) -> str:
    context = build_context(state)
    fallback = (
        "Je ne peux pas repondre precisement sans le module de dialogue Qwen actif, mais le plan et les "
        "incoherences ci-dessus contiennent les faits sources pour repondre a cette question."
    )
    return call_llm(
        PROMPT, context,
        f"Le gerant demande: \"{question}\". Reponds uniquement a partir du contexte fourni, en citant "
        f"les sources. Si le contexte ne permet pas de repondre, dis-le clairement.",
        fallback,
    )
