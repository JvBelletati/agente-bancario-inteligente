import logging
from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from langchain_core.messages import AIMessage
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_ENTREVISTA
from src.tools.score import atualizar_score_cliente
from src.tools.common import retornar_para_credito, encerrar
from src.data.repository import mascarar_cpf

logger = logging.getLogger(__name__)


def entrevista_node(state: BankState) -> Command[Literal["credito"]]:
    cpf = state.get("cpf")
    logger.info("[FLUXO] → nó ENTREVISTA (cpf=%s)", mascarar_cpf(cpf))

    def _atualizar_score_cliente(renda: float, tipo_emprego: str, despesas: float,
                                 num_dependentes: int, tem_dividas: str) -> dict:
        """Recalcula e persiste o score com os dados coletados na entrevista."""
        return atualizar_score_cliente(cpf, renda, tipo_emprego, despesas,
                                       num_dependentes, tem_dividas)

    funcs = [_atualizar_score_cliente, retornar_para_credito, encerrar]
    novas, resultados = run_react_turn(state, PROMPT_ENTREVISTA, funcs)
    update = {"messages": novas}
    novo_score = None

    for r in resultados:
        if r["name"] == "encerrar":
            logger.info("[ENTREVISTA] encerramento solicitado pelo cliente")
            return Command(goto=END, update={**update, "encerrar": True})
        if r["name"] == "_atualizar_score_cliente" and r["out"].get("novo_score") is not None:
            novo_score = r["out"]["novo_score"]
            # atualiza cliente em memória p/ o Crédito reavaliar com o score novo
            cliente = dict(state.get("cliente") or {})
            cliente["score"] = novo_score
            update["cliente"] = cliente
        if r["out"].get("handoff") == "credito":
            logger.info("[FLUXO] handoff: entrevista → crédito (reanálise)")
            nota = AIMessage(content="Com seu score atualizado, vou reanalisar seu pedido de limite.")
            update["messages"] = novas + [nota]
            return Command(goto="credito", update={**update, "active_agent": "credito"})

    return Command(goto=END, update=update)  # continua a entrevista no próximo turno (sticky via gate_auth)
