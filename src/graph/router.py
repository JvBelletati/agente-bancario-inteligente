import logging
from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel
from src.graph.state import BankState
from src.config import get_llm
from src.prompts.personas import PROMPT_ROUTER

logger = logging.getLogger(__name__)


def gate_auth(state: BankState) -> Command[Literal["triagem", "router", "credito", "entrevista", "cambio"]]:
    if state.get("encerrar"):
        logger.info("[FLUXO] gate_auth: encerrar=True → END")
        return Command(goto=END)
    if not state.get("autenticado"):
        logger.info("[FLUXO] gate_auth: não autenticado → triagem")
        return Command(goto="triagem")
    ativo = state.get("active_agent")
    if ativo in ("credito", "entrevista", "cambio"):
        logger.info("[FLUXO] gate_auth: especialista ativo (sticky) → %s", ativo)
        return Command(goto=ativo)
    logger.info("[FLUXO] gate_auth: autenticado, sem especialista → router")
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
        logger.exception("[FLUXO] router: falha ao classificar intenção → fallback 'credito'")
        destino = "credito"  # fallback seguro
    logger.info("[FLUXO] router: intenção classificada → %s", destino)
    return Command(goto=destino, update={"active_agent": destino})
