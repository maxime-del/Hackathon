"""
Orchestrateur: appelle chaque specialiste dans l'ordre et fait circuler
l'etat partage (blackboard). C'est le seul point d'entree que app.py
doit appeler.
"""
from core.state import EngineState
from agents import anomaly_agent, decider_agent, graph_agent, risk_agent, translator_agent


def run(process_id: str = "P01") -> EngineState:
    state = EngineState(process_id=process_id)
    state = graph_agent.run(state)
    state = anomaly_agent.run(state)
    state = risk_agent.run(state)
    state = decider_agent.run(state)
    state = translator_agent.run(state)
    return state
