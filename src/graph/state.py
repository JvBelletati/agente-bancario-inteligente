from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class BankState(TypedDict):
    messages: Annotated[list, add_messages]
    autenticado: bool
    tentativas_auth: int
    cpf: str | None
    cliente: dict | None
    active_agent: str
    ultima_solicitacao: dict | None
    dados_entrevista: dict | None
    encerrar: bool
