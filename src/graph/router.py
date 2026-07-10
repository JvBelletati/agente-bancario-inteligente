from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel
from src.graph.state import BankState
from src.config import get_llm
from src.prompts.personas import PROMPT_ROUTER


def gate_auth(state: BankState) -> Command[Literal["triagem", "router", "credito", "entrevista", "cambio"]]:
    if state.get("encerrar"):
        return Command(goto=END)
    if not state.get("autenticado"):
        return Command(goto="triagem")
    ativo = state.get("active_agent")
    if ativo in ("credito", "entrevista", "cambio"):
        return Command(goto=ativo)
    return Command(goto="router")


class _Rota(BaseModel):
    destino: Literal["credito", "cambio"]


def router_node(state: BankState) -> Command[Literal["credito", "cambio"]]:
    from langchain_core.messages import SystemMessage
    llm = get_llm().with_structured_output(_Rota)
    try:
        rota = llm.invoke([SystemMessage(content=PROMPT_ROUTER), *state["messages"]])
        destino = rota.destino
    except Exception:
        destino = "credito"  # fallback seguro
    return Command(goto=destino, update={"active_agent": destino})
