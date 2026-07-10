from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.graph import agent_runtime


def _ai_com_toolcall(nome, args):
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args, "id": "call_1"}])


def _ai_final(texto):
    return AIMessage(content=texto)


def test_run_react_turn_executa_tool_e_coleta_resultado():
    def minha_tool(x: int) -> dict:
        """soma 1"""
        return {"valor": x + 1, "mensagem": f"resultado {x+1}"}

    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    fake_llm.invoke.side_effect = [_ai_com_toolcall("minha_tool", {"x": 4}), _ai_final("pronto")]

    state = {"messages": [HumanMessage(content="oi")]}
    with patch("src.graph.agent_runtime.get_llm", return_value=fake_llm):
        novas, resultados = agent_runtime.run_react_turn(state, "system", [minha_tool])

    assert resultados[0]["out"]["valor"] == 5
    assert novas[-1].content == "pronto"


def test_run_react_turn_toolmessage_never_empty():
    def handoff_tool() -> dict:
        """sinaliza handoff"""
        return {"handoff": "entrevista", "mensagem": ""}

    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    fake_llm.invoke.side_effect = [
        _ai_com_toolcall("handoff_tool", {}),
        _ai_final("ok"),
    ]

    state = {"messages": [HumanMessage(content="oi")]}
    with patch("src.graph.agent_runtime.get_llm", return_value=fake_llm):
        novas, resultados = agent_runtime.run_react_turn(state, "system", [handoff_tool])

    tool_messages = [m for m in novas if isinstance(m, ToolMessage)]
    assert tool_messages
    tm = tool_messages[0]
    assert tm.content
    assert tm.content != ""
