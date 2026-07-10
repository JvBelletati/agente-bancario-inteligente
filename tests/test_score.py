import pytest
from src.tools.score import calcular_score


def test_score_formal_sem_dependentes_sem_dividas():
    # (5000/(2000+1))*30 = 74.96 ; +300 formal +100 dep0 +100 sem dívida = 574.96 -> 575
    assert calcular_score(5000, "formal", 2000, 0, "não") == 575


def test_score_clamp_maximo():
    assert calcular_score(1_000_000, "formal", 0, 0, "não") == 1000


def test_score_clamp_minimo():
    assert calcular_score(0, "desempregado", 5000, 3, "sim") == 0


def test_bucket_dependentes_3_ou_mais():
    base = calcular_score(3000, "formal", 1000, 2, "não")
    tres_mais = calcular_score(3000, "formal", 1000, 5, "não")
    assert tres_mais < base  # peso 30 (3+) < 60 (2)


def test_normaliza_emprego_sem_acento_e_maiuscula():
    assert calcular_score(3000, "AUTONOMO", 1000, 0, "não") == calcular_score(3000, "autônomo", 1000, 0, "não")


def test_normaliza_dividas_sinonimos():
    assert calcular_score(3000, "formal", 1000, 0, "s") == calcular_score(3000, "formal", 1000, 0, "sim")


def test_entrada_negativa_levanta_erro():
    with pytest.raises(ValueError):
        calcular_score(-1, "formal", 1000, 0, "não")
