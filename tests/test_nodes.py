from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from src.graph.builder import estado_inicial
from src.graph.nodes.credito import credito_node
from src.graph.router import gate_auth

CLIENTE = {"cpf": "12345678901", "nome": "Ana", "data_nascimento": "1990-05-14",
           "limite_atual": 2000.0, "score": 620}
TABELA = [{"score_min": 500, "score_max": 699, "limite_maximo": 5000.0}]


def test_credito_node_threads_registered_data_hora():
    """Pina o FIX 1: data_hora deve ser resolvida internamente (via _ctx), não pelo LLM.

    O 2º tool call NÃO informa data_hora (o modelo nunca a vê, conforme run_react_turn
    só expõe o campo `mensagem` de volta ao LLM). Antes do FIX 1, a assinatura antiga de
    `_avaliar_score_limite(novo_limite, data_hora)` geraria TypeError (capturado
    silenciosamente por run_react_turn) e `atualizar_status_solicitacao` jamais seria
    chamada. Depois do FIX 1, a data_hora registrada é reaproveitada internamente e o
    fluxo completa com sucesso.
    """
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    fake_llm.invoke.side_effect = [
        AIMessage(content="", tool_calls=[{
            "name": "_registrar_solicitacao_aumento",
            "args": {"novo_limite": 4000.0},
            "id": "c1",
        }]),
        AIMessage(content="", tool_calls=[{
            "name": "_avaliar_score_limite",
            "args": {"novo_limite": 4000.0},
            "id": "c2",
        }]),
        AIMessage(content="Seu pedido foi avaliado."),
    ]

    estado = estado_inicial()
    estado.update({
        "messages": [HumanMessage(content="quero aumentar para 4000")],
        "autenticado": True,
        "cpf": "12345678901",
        "cliente": CLIENTE,
        "active_agent": "credito",
        "ultima_solicitacao": None,
    })

    with patch("src.graph.agent_runtime.get_llm", return_value=fake_llm), \
         patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE), \
         patch("src.tools.credito.carregar_tabela_score", return_value=TABELA), \
         patch("src.tools.credito.append_solicitacao") as append_mock, \
         patch("src.tools.credito.atualizar_status_solicitacao") as atualizar_mock:
        credito_node(estado)

    append_mock.assert_called_once()
    atualizar_mock.assert_called_once()

    data_hora_registrada = append_mock.call_args[0][3]
    data_hora_avaliada = atualizar_mock.call_args[0][1]
    assert data_hora_registrada == data_hora_avaliada


def test_gate_auth_sticky_and_gate():
    nao_autenticado = estado_inicial()
    assert gate_auth(nao_autenticado).goto == "triagem"

    autenticado_credito = estado_inicial()
    autenticado_credito["autenticado"] = True
    autenticado_credito["active_agent"] = "credito"
    assert gate_auth(autenticado_credito).goto == "credito"

    encerrando = estado_inicial()
    encerrando["encerrar"] = True
    assert gate_auth(encerrando).goto == END
