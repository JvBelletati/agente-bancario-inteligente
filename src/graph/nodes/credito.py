from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_CREDITO
from src.tools.credito import (
    consultar_limite, registrar_solicitacao_aumento, avaliar_score_limite,
)
from src.tools.common import iniciar_entrevista_credito, outro_assunto, encerrar


def credito_node(state: BankState) -> Command[Literal["entrevista", "router"]]:
    cpf = state.get("cpf")

    def _consultar_limite() -> dict:
        """Consulta o limite de crédito atual do cliente autenticado."""
        return consultar_limite(cpf)

    def _registrar_solicitacao_aumento(novo_limite: float) -> dict:
        """Registra um pedido de aumento de limite (status pendente)."""
        return registrar_solicitacao_aumento(cpf, novo_limite)

    def _avaliar_score_limite(novo_limite: float, data_hora: str) -> dict:
        """Avalia o pedido de aumento contra o score do cliente."""
        return avaliar_score_limite(cpf, novo_limite, data_hora)

    funcs = [_consultar_limite, _registrar_solicitacao_aumento, _avaliar_score_limite,
             iniciar_entrevista_credito, outro_assunto, encerrar]
    novas, resultados = run_react_turn(state, PROMPT_CREDITO, funcs)
    update = {"messages": novas}

    for r in resultados:
        out = r["out"]
        if r["name"] == "_registrar_solicitacao_aumento":
            update["ultima_solicitacao"] = out
        if r["name"] == "encerrar":
            return Command(goto=END, update={**update, "encerrar": True})
        if out.get("handoff") == "entrevista":
            return Command(goto="entrevista", update={**update, "active_agent": "entrevista"})
        if out.get("handoff") == "router":
            return Command(goto="router", update={**update, "active_agent": ""})

    return Command(goto=END, update=update)  # respondeu e aguarda o cliente (fica sticky via gate_auth)
