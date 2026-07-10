from unittest.mock import patch
import src.tools.credito as credito

TABELA = [
    {"score_min": 0, "score_max": 299, "limite_maximo": 500.0},
    {"score_min": 500, "score_max": 699, "limite_maximo": 5000.0},
    {"score_min": 700, "score_max": 849, "limite_maximo": 15000.0},
]
CLIENTE = {"cpf": "12345678901", "nome": "Ana", "data_nascimento": "1990-05-14",
           "limite_atual": 2000.0, "score": 620}


def test_limite_maximo_para_score_borda_inferior():
    assert credito.limite_maximo_para_score(500, TABELA) == 5000.0


def test_limite_maximo_para_score_borda_superior():
    assert credito.limite_maximo_para_score(699, TABELA) == 5000.0


def test_limite_maximo_para_score_fora_da_tabela_retorna_zero():
    assert credito.limite_maximo_para_score(999, TABELA) == 0.0


def test_consultar_limite():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE):
        r = credito.consultar_limite("12345678901")
    assert r["limite_atual"] == 2000.0


def test_registrar_solicitacao_status_pendente():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE), \
         patch("src.tools.credito.append_solicitacao") as ap:
        r = credito.registrar_solicitacao_aumento("12345678901", 4000.0)
    assert r["status"] == "pendente"
    assert r["limite_atual"] == 2000.0
    ap.assert_called_once()


def test_avaliar_aprovado_quando_dentro_do_teto():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE), \
         patch("src.tools.credito.carregar_tabela_score", return_value=TABELA), \
         patch("src.tools.credito.atualizar_status_solicitacao") as upd:
        r = credito.avaliar_score_limite("12345678901", 4000.0, "2026-07-10T10:00:00")
    assert r["status"] == "aprovado"  # score 620 -> teto 5000 >= 4000
    upd.assert_called_once_with("12345678901", "2026-07-10T10:00:00", "aprovado")


def test_avaliar_rejeitado_quando_acima_do_teto():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE), \
         patch("src.tools.credito.carregar_tabela_score", return_value=TABELA), \
         patch("src.tools.credito.atualizar_status_solicitacao"):
        r = credito.avaliar_score_limite("12345678901", 9000.0, "2026-07-10T10:00:00")
    assert r["status"] == "rejeitado"  # teto 5000 < 9000
