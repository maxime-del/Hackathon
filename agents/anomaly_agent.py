"""
Specialiste "incoherences": fait tourner les controles deterministes sur
les CSV, enrichit certains constats avec un passage retrouve par le RAG
dans les documents texte (PRA, rapport d'incident...), puis demande a
Qwen une synthese courte - jamais l'inverse.
"""
from pathlib import Path

from core.llm import call_llm
from core.schemas import Finding
from core.state import EngineState
from tools.anomaly_checks import run_anomaly_checks
from tools.retrieval import search

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "anomaly.md").read_text()

# Pour ces anomalies, on va chercher un extrait reel dans les documents
# texte via le RAG afin de citer une phrase source, plutot qu'une
# description ecrite a la main.
RAG_QUERIES = {
    "PRA_OBSOLETE_AD": "Active Directory operationnel prerequis PRA",
    "SECRETS_VAULT_BLOCKER": "coffre-fort secrets vault restaurer",
}


def _to_finding(a) -> Finding:
    return Finding(
        id=a.id, severity=a.severity, title_tech=a.title_tech, title_human=a.title_human,
        detail_tech=a.detail_tech, detail_human=a.detail_human, sources=a.sources,
        action_pro=a.action_pro,
    )


def run(state: EngineState) -> EngineState:
    graph_nodes = set(state.graph.nodes) if state.graph is not None else set()
    anomalies = run_anomaly_checks(state.process_id, graph_nodes)
    findings = [_to_finding(a) for a in anomalies]

    for f in findings:
        query = RAG_QUERIES.get(f.id)
        if not query:
            continue
        passages = search(query, k=1)
        if passages:
            p = passages[0]
            f.detail_tech += f" Extrait retrouve dans {p.source}: \"{p.text}\"."
            if p.source not in f.sources:
                f.sources.append(p.source)

    state.findings = findings

    context = "\n".join(
        f"- [{f.severity}] {f.title_tech} (sources: {', '.join(f.sources)})" for f in findings
    )
    critical = [f for f in findings if f.severity == "CRITIQUE"]
    fallback = (
        f"{len(findings)} incoherences detectees dans le corpus, dont {len(critical)} critiques. "
        f"Les plus urgentes : {'; '.join(f.title_tech for f in critical[:3])}."
    )
    state.anomaly_narrative = call_llm(PROMPT, context, "Synthetise les anomalies en 3-4 phrases.", fallback)
    return state
