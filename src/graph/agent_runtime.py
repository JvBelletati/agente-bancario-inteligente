import logging
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from src.config import get_llm

logger = logging.getLogger(__name__)


def as_tool(fn) -> StructuredTool:
    return StructuredTool.from_function(fn)


def run_react_turn(state, system_prompt: str, funcs: list, max_iters: int = 6):
    """Executa um turno ReAct limitado para um nó.

    funcs: lista de funções Python (plain) que este agente pode chamar.
    Retorna (novas_mensagens, resultados):
      - novas_mensagens: AIMessage/ToolMessage geradas neste turno (p/ add_messages)
      - resultados: dicts retornados pelas tools chamadas (o nó pós-processa em estado/goto)
    """
    by_name = {f.__name__: f for f in funcs}
    tools = [as_tool(f) for f in funcs]
    llm = get_llm().bind_tools(tools) if tools else get_llm()

    conversa = [SystemMessage(content=system_prompt), *state["messages"]]
    novas = []
    resultados = []

    for _ in range(max_iters):
        ai = llm.invoke(conversa)
        conversa.append(ai)
        novas.append(ai)
        if not getattr(ai, "tool_calls", None):
            return novas, resultados
        for call in ai.tool_calls:
            fn = by_name.get(call["name"])
            if fn is None:
                out = {"mensagem": f"Ação {call['name']} indisponível."}
            else:
                try:
                    out = fn(**call["args"])
                except Exception as e:  # falha graciosa
                    logger.exception("Erro na tool %s: %s", call["name"], e)
                    out = {"mensagem": "Tive um problema ao executar essa ação."}
            resultados.append({"name": call["name"], "args": call["args"], "out": out})
            tm = ToolMessage(content=str(out.get("mensagem") or out), tool_call_id=call["id"])
            conversa.append(tm)
            novas.append(tm)
    return novas, resultados
