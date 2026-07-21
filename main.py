from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("API_KEY")

llm = ChatOpenAI(
    model="qwen3.6-27b",
    api_key=api_key,
    base_url="https://ai-api.gpu-1.k8s.cri.epita.fr/v1",
    temperature=0.3,
)


@tool
def get_weather(ville: str) -> str:
    """Retourne la météo actuelle pour une ville donnée."""
    # ta logique ici (appel API météo réelle)
    return f"Il fait beau à {ville}, 22°C."

@tool
def calculer(expression: str) -> str:
    """Évalue une expression mathématique simple."""
    return str(eval(expression))

tools = [get_weather, calculer]

agent = create_react_agent(llm, tools)

response = agent.invoke({
    "messages": [{"role": "user", "content": "Quel temps fait-il à Paris ?"}]
})

print(response["messages"][-1].content)