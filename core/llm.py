"""
Point d'entree unique vers Qwen. Tous les agents passent par ici pour
appeler le LLM - un seul endroit ou changer de modele/endpoint/cle.

Contrat: le LLM ne fait jamais de calcul. On lui donne un contexte de
faits deja etablis par les tools deterministes, et on exige une reponse
qui cite ses sources. Si aucune cle API n'est configuree ou que l'appel
echoue, on retombe sur un texte de secours fourni par l'appelant - la
demo ne doit jamais dependre d'un reseau disponible.
"""
import os
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "qwen3.6-27b"
BASE_URL = "https://ai-api.gpu-1.k8s.cri.epita.fr/v1"

_client = None
_available = None
_big_client = None


def _build_client(max_tokens: int, timeout: int):
    from langchain_openai import ChatOpenAI
    api_key = os.getenv("API_KEY")
    return ChatOpenAI(
        model=MODEL_NAME, api_key=api_key, base_url=BASE_URL,
        temperature=0.2, timeout=timeout, max_tokens=max_tokens,
        # Qwen3 est un modele "raisonneur": sans ce flag, il peut passer
        # plusieurs dizaines de secondes (et tout son budget de tokens) a
        # "reflechir" avant d'ecrire la reponse - parfois sans jamais
        # rediger de contenu si max_tokens est atteint pendant la
        # reflexion. On coupe ce raisonnement etendu: la demo a besoin
        # de reponses courtes et rapides, pas d'un raisonnement visible.
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def get_llm():
    """Client rapide pour les narrations courtes (3-6 phrases)."""
    global _client, _available
    if _available is not None:
        return _client
    api_key = os.getenv("API_KEY")
    if not api_key:
        _available = False
        return None
    try:
        _client = _build_client(max_tokens=600, timeout=30)
        _available = True
    except Exception:
        _client = None
        _available = False
    return _client


def get_big_llm():
    """Client pour les taches lourdes a sortie structuree (analyse JSON sur
    plusieurs constats) - budget de tokens et timeout plus genereux, donc
    plus lent. A utiliser uniquement quand une reponse courte ne suffit pas."""
    global _big_client
    if not llm_is_available():
        return None
    if _big_client is None:
        try:
            _big_client = _build_client(max_tokens=1600, timeout=120)
        except Exception:
            _big_client = None
    return _big_client


def llm_is_available() -> bool:
    get_llm()
    return bool(_available)


def _invoke(client, system_prompt: str, context: str, instruction: str, fallback: str) -> str:
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        resp = client.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"CONTEXTE (faits deja calcules, sources fiables):\n{context}\n\nTACHE:\n{instruction}"),
        ])
        text = resp.content.strip()
        return text if text else fallback
    except Exception:
        return fallback


def call_llm(system_prompt: str, context: str, instruction: str, fallback: str) -> str:
    client = get_llm()
    if client is None:
        return fallback
    return _invoke(client, system_prompt, context, instruction, fallback)


def call_llm_big(system_prompt: str, context: str, instruction: str, fallback: str) -> str:
    """Comme call_llm, mais avec un budget de tokens/temps plus genereux -
    pour les analyses qui doivent produire plusieurs constats structures."""
    client = get_big_llm()
    if client is None:
        return fallback
    return _invoke(client, system_prompt, context, instruction, fallback)
