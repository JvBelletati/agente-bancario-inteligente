import logging
from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_CAMBIO
from src.tools.cambio import consultar_cotacao
from src.tools.common import outro_assunto, encerrar

logger = logging.getLogger(__name__)


def cambio_node(state: BankState) -> Command[Literal["router"]]:
    logger.info("[FLUXO] → nó CÂMBIO")
    novas, resultados = run_react_turn(state, PROMPT_CAMBIO, [consultar_cotacao, outro_assunto, encerrar])
    update = {"messages": novas}
    for r in resultados:
        if r["name"] == "encerrar":
            logger.info("[CÂMBIO] encerramento solicitado pelo cliente")
            return Command(goto=END, update={**update, "encerrar": True})
        if r["out"].get("handoff") == "router":
            logger.info("[FLUXO] handoff: câmbio → router (outro assunto)")
            return Command(goto="router", update={**update, "active_agent": ""})
    return Command(goto=END, update=update)  # respondeu e aguarda o cliente (sticky via gate_auth)
