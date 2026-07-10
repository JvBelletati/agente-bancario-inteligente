from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage
from src.graph.builder import build_graph, estado_inicial

CLIENTE = {"cpf": "12345678901", "nome": "Ana Souza",
           "data_nascimento": "1990-05-14", "limite_atual": 2000.0, "score": 620}


def test_gate_forca_triagem_e_autentica():
    # gate_auth (não autenticado) -> triagem -> autenticar_cliente (ok) -> saudação -> END.
    # O router só entra no PRÓXIMO turno; aqui provamos o gate + a autenticação determinística.
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    fake_llm.invoke.side_effect = [
        AIMessage(content="", tool_calls=[{"name": "autenticar_cliente",
                 "args": {"cpf": "12345678901", "data_nascimento": "1990-05-14"}, "id": "c1"}]),
        AIMessage(content="Perfeito, Ana! Em que posso ajudar?"),
    ]

    with patch("src.graph.agent_runtime.get_llm", return_value=fake_llm), \
         patch("src.tools.auth.buscar_cliente", return_value=CLIENTE):
        graph = build_graph()
        estado = estado_inicial()
        estado["messages"] = [HumanMessage(content="Meu CPF é 123.456.789-01, nasci 1990-05-14")]
        cfg = {"configurable": {"thread_id": "t1"}}
        final = graph.invoke(estado, cfg)

    assert final["autenticado"] is True
    assert final["cpf"] == "12345678901"
    assert final["active_agent"] == ""  # aguarda o pedido do cliente; router entra no próximo turno
