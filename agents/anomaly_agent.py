"""
Specialiste "incoherences": un seul controle reste deterministe (l'ecart
BIA declare vs graphe reel, generique). Tout le reste est desormais une
vraie analyse Qwen de la fiche de faits par actif (tools/asset_facts.py) -
le LLM doit reellement lire les donnees et trouver ce qui cloche, il ne
reconnait plus des identifiants connus a l'avance. On enrichit ensuite
chaque constat avec un passage RAG reel s'il en existe un pertinent.

Contrepartie assumee : cette partie n'est plus 100% deterministe (le LLM
peut varier d'un run a l'autre, ou se tromper) - c'est le prix a payer
pour fonctionner sur un corpus jamais vu. Si Qwen est indisponible, on
retombe uniquement sur le controle BIA (mieux que rien, jamais un plantage).
"""
import json
import re
from pathlib import Path

from core.llm import call_llm_big
from core.schemas import Finding
from core.state import EngineState
from tools.anomaly_checks import bia_gap_finding
from tools.asset_facts import build_fact_sheet
from tools.data_loader import load_all
from tools.retrieval import search

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "anomaly.md").read_text()

VALID_SEVERITIES = {"CRITIQUE", "HAUTE", "MOYENNE"}


def _parse_findings_json(text: str) -> list[dict]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def _to_finding(raw: dict, seen_ids: set[str]) -> Finding | None:
    if not isinstance(raw, dict):
        return None
    title_tech = str(raw.get("title_tech") or "").strip()
    if not title_tech:
        return None
    finding_id = str(raw.get("id") or title_tech)[:60].strip().replace(" ", "_") or title_tech
    while finding_id in seen_ids:
        finding_id += "_"
    seen_ids.add(finding_id)

    severity = str(raw.get("severity") or "MOYENNE").upper()
    if severity not in VALID_SEVERITIES:
        severity = "MOYENNE"

    sources = [s for s in (raw.get("sources") or []) if isinstance(s, str)]
    asset = raw.get("asset")
    asset = str(asset).strip() if isinstance(asset, str) and asset.strip() else None
    action_pro = raw.get("action_pro")
    action_pro = str(action_pro).strip() if isinstance(action_pro, str) and action_pro.strip() else None

    return Finding(
        id=finding_id, severity=severity, title_tech=title_tech,
        title_human=str(raw.get("title_human") or title_tech),
        detail_tech=str(raw.get("detail_tech") or ""),
        detail_human=str(raw.get("detail_human") or raw.get("detail_tech") or ""),
        sources=sources, action_pro=action_pro, asset=asset,
    )


def run(state: EngineState) -> EngineState:
    graph_nodes = set(state.graph.nodes) if state.graph is not None else set()
    tables = load_all()

    findings: list[Finding] = []
    seen_ids: set[str] = set()

    bia_finding = bia_gap_finding(state.process_id, graph_nodes)
    if bia_finding:
        findings.append(Finding(
            id=bia_finding.id, severity=bia_finding.severity, title_tech=bia_finding.title_tech,
            title_human=bia_finding.title_human, detail_tech=bia_finding.detail_tech,
            detail_human=bia_finding.detail_human, sources=bia_finding.sources, asset=bia_finding.asset,
        ))
        seen_ids.add(bia_finding.id)

    other_assets = sorted(graph_nodes - {state.process_id})
    if other_assets:
        fact_sheet = build_fact_sheet(tables, other_assets, state.process_id)
        raw_response = call_llm_big(
            PROMPT, fact_sheet,
            "Analyse cette fiche de faits et identifie les incoherences/risques reellement demontres "
            "(reponds uniquement avec le tableau JSON demande, 5 constats maximum, tres concis).",
            fallback="[]",
        )
        for raw in _parse_findings_json(raw_response)[:5]:
            finding = _to_finding(raw, seen_ids)
            if finding is None:
                continue
            if finding.asset:
                passages = search(f"{finding.asset} {finding.title_tech}", k=1)
                if passages and passages[0].score > 0.15:
                    p = passages[0]
                    finding.detail_tech += f" Extrait retrouve dans {p.source}: \"{p.text}\"."
                    if p.source not in finding.sources:
                        finding.sources.append(p.source)
            findings.append(finding)

    state.findings = findings

    severity_order = {"CRITIQUE": 0, "HAUTE": 1, "MOYENNE": 2}
    state.findings.sort(key=lambda f: severity_order.get(f.severity, 9))

    # Synthese batie deterministiquement a partir des constats (deja
    # rediges en langage clair par l'analyse ci-dessus) - pas de nouvel
    # appel LLM ici : ca reduirait encore la latence et le prompt JSON
    # ci-dessus ne convient de toute facon pas a une synthese en prose.
    critical = [f for f in findings if f.severity == "CRITIQUE"]
    if critical:
        state.anomaly_narrative = (
            f"{len(findings)} incoherence(s) detectee(s), dont {len(critical)} critique(s). "
            f"Les plus urgentes : {'; '.join(f.title_human for f in critical[:3])}."
        )
    elif findings:
        state.anomaly_narrative = (
            f"{len(findings)} incoherence(s) detectee(s), aucune classee critique. "
            f"La plus notable : {findings[0].title_human}"
        )
    else:
        state.anomaly_narrative = "Aucune anomalie identifiee sur les donnees fournies."
    return state
