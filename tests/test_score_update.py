from unittest.mock import patch
from src.tools.score import atualizar_score_cliente


def test_atualiza_score_persiste_e_retorna_valor():
    with patch("src.tools.score.atualizar_score") as upd:
        r = atualizar_score_cliente("12345678901", 5000, "formal", 2000, 0, "não")
    assert r["novo_score"] == 575
    upd.assert_called_once_with("12345678901", 575)


def test_entrada_invalida_retorna_mensagem_sem_quebrar():
    with patch("src.tools.score.atualizar_score") as upd:
        r = atualizar_score_cliente("12345678901", -1, "formal", 2000, 0, "não")
    assert r["novo_score"] is None
    assert "não" in r["mensagem"].lower() or "inv" in r["mensagem"].lower()
    upd.assert_not_called()
