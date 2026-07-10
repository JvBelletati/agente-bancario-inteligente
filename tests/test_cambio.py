from unittest.mock import patch, MagicMock
import httpx
from src.tools.cambio import consultar_cotacao


def _resp(json_data, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data
    return m


def test_cotacao_sucesso():
    payload = {"USDBRL": {"bid": "5.43", "name": "Dólar Americano/Real Brasileiro"}}
    with patch("src.tools.cambio.httpx.get", return_value=_resp(payload)):
        r = consultar_cotacao("USD")
    assert r["valor"] == 5.43
    assert "5.43" in r["mensagem"]


def test_cotacao_status_erro():
    with patch("src.tools.cambio.httpx.get", return_value=_resp({}, status=404)):
        r = consultar_cotacao("XXX")
    assert r["valor"] is None
    assert isinstance(r["mensagem"], str)


def test_cotacao_timeout_nao_quebra():
    with patch("src.tools.cambio.httpx.get", side_effect=httpx.TimeoutException("t")):
        r = consultar_cotacao("USD")
    assert r["valor"] is None
    assert "não" in r["mensagem"].lower() or "instab" in r["mensagem"].lower()
