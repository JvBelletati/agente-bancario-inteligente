from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from src.graph.state import BankState


def gate_auth(state: BankState) -> Command[Literal["triagem", "router", "credito", "entrevista", "cambio"]]:
    if state.get("encerrar"):
        return Command(goto=END)
    if not state.get("autenticado"):
        return Command(goto="triagem")
    ativo = state.get("active_agent")
    if ativo in ("credito", "entrevista", "cambio"):
        return Command(goto=ativo)
    return Command(goto="router")
