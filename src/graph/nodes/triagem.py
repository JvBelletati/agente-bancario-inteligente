from langgraph.graph import END
from langgraph.types import Command
from src.config import MAX_TENTATIVAS_AUTH
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_TRIAGEM
from src.tools.auth import autenticar_cliente
from src.tools.common import encerrar


def triagem_node(state: BankState) -> Command:
    novas, resultados = run_react_turn(state, PROMPT_TRIAGEM, [autenticar_cliente, encerrar])
    update = {"messages": novas}

    for r in resultados:
        if r["name"] == "encerrar":
            return Command(goto=END, update={**update, "encerrar": True})
        if r["name"] == "autenticar_cliente":
            out = r["out"]
            if out.get("autenticado"):
                update.update({
                    "autenticado": True,
                    "cpf": out["cliente"]["cpf"],
                    "cliente": out["cliente"],
                    "active_agent": "",
                })
                return Command(goto=END, update=update)  # saúda e aguarda o pedido (router entra no próximo turno via gate_auth)
            # falha de autenticação
            tentativas = state.get("tentativas_auth", 0) + 1
            update["tentativas_auth"] = tentativas
            if tentativas >= MAX_TENTATIVAS_AUTH:
                from langchain_core.messages import AIMessage
                despedida = AIMessage(content=(
                    "Infelizmente não consegui confirmar seus dados após algumas tentativas. "
                    "Por segurança, vou encerrar por aqui. Você pode tentar novamente mais tarde. "
                    "Tenha um ótimo dia!"))
                update["messages"] = novas + [despedida]
                update["encerrar"] = True
                return Command(goto=END, update=update)
            return Command(goto=END, update=update)  # aguarda nova tentativa do cliente

    # sem tool call → pediu os dados e aguarda a resposta do cliente
    return Command(goto=END, update=update)
