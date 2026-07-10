from unittest.mock import patch
from src.tools.auth import autenticar_cliente

CLIENTE = {"cpf": "12345678901", "nome": "Ana Souza",
           "data_nascimento": "1990-05-14", "limite_atual": 2000.0, "score": 620}


def test_auth_sucesso():
    with patch("src.tools.auth.buscar_cliente", return_value=CLIENTE):
        r = autenticar_cliente("123.456.789-01", "1990-05-14")
    assert r["autenticado"] is True
    assert r["cliente"]["nome"] == "Ana Souza"


def test_auth_falha_retorna_cliente_none():
    with patch("src.tools.auth.buscar_cliente", return_value=None):
        r = autenticar_cliente("00000000000", "2000-01-01")
    assert r["autenticado"] is False
    assert r["cliente"] is None
    assert isinstance(r["mensagem"], str)
