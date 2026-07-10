from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from src.graph.state import BankState
from src.graph.router import gate_auth, router_node
from src.graph.nodes.triagem import triagem_node
from src.graph.nodes.credito import credito_node
from src.graph.nodes.entrevista import entrevista_node
from src.graph.nodes.cambio import cambio_node


def estado_inicial() -> dict:
    return {
        "messages": [],
        "autenticado": False,
        "tentativas_auth": 0,
        "cpf": None,
        "cliente": None,
        "active_agent": "",
        "ultima_solicitacao": None,
        "dados_entrevista": None,
        "encerrar": False,
    }


def build_graph():
    g = StateGraph(BankState)
    g.add_node("gate_auth", gate_auth)
    g.add_node("triagem", triagem_node)
    g.add_node("router", router_node)
    g.add_node("credito", credito_node)
    g.add_node("entrevista", entrevista_node)
    g.add_node("cambio", cambio_node)
    g.add_edge(START, "gate_auth")
    # demais arestas são dinâmicas via Command(goto=...)
    return g.compile(checkpointer=MemorySaver())
