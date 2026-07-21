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


def get_llm():
    global _client, _available
    if _available is not None:
        return _client
    api_key = os.getenv("API_KEY")
    if not api_key:
        _available = False
        return None
    try:
        from langchain_openai import ChatOpenAI
        _client = ChatOpenAI(model=MODEL_NAME, api_key=api_key, base_url=BASE_URL,
                              temperature=0.2, timeout=20)
        _available = True
    except Exception:
        _client = None
        _available = False
    return _client


def llm_is_available() -> bool:
    get_llm()
    return bool(_available)


def call_llm(system_prompt: str, context: str, instruction: str, fallback: str) -> str:
    client = get_llm()
    if client is None:
        return fallback
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
