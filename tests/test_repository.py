import csv
import pytest
from src.data import repository as repo


@pytest.fixture
def fake_data(tmp_path, monkeypatch):
    clientes = tmp_path / "clientes.csv"
    with open(clientes, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cpf", "nome", "data_nascimento", "limite_atual", "score"])
        w.writerow(["12345678901", "Ana Souza", "1990-05-14", "2000.00", "620"])
    score_tab = tmp_path / "score_limite.csv"
    with open(score_tab, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score_min", "score_max", "limite_maximo"])
        w.writerow(["500", "699", "5000.00"])
        w.writerow(["700", "849", "15000.00"])
    solic = tmp_path / "solicitacoes.csv"
    monkeypatch.setattr(repo, "CLIENTES_CSV", clientes)
    monkeypatch.setattr(repo, "SCORE_LIMITE_CSV", score_tab)
    monkeypatch.setattr(repo, "SOLICITACOES_CSV", solic)
    return tmp_path


def test_normalizar_cpf_remove_formatacao():
    assert repo.normalizar_cpf("123.456.789-01") == "12345678901"


def test_buscar_cliente_match(fake_data):
    c = repo.buscar_cliente("123.456.789-01", "1990-05-14")
    assert c is not None
    assert c["nome"] == "Ana Souza"
    assert c["score"] == 620
    assert c["limite_atual"] == 2000.00


def test_buscar_cliente_data_errada(fake_data):
    assert repo.buscar_cliente("12345678901", "1991-01-01") is None


def test_atualizar_score_persiste(fake_data):
    repo.atualizar_score("12345678901", 800)
    c = repo.obter_cliente_por_cpf("12345678901")
    assert c["score"] == 800


def test_carregar_tabela_score(fake_data):
    tab = repo.carregar_tabela_score()
    assert tab[0] == {"score_min": 500, "score_max": 699, "limite_maximo": 5000.00}


def test_append_e_atualizar_status_solicitacao(fake_data):
    repo.append_solicitacao("12345678901", 2000.0, 4000.0, "2026-07-10T10:00:00")
    repo.atualizar_status_solicitacao("12345678901", "2026-07-10T10:00:00", "aprovado")
    with open(fake_data / "solicitacoes.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[-1]["status_pedido"] == "aprovado"
    assert rows[-1]["novo_limite_solicitado"] == "4000.0"


def test_buscar_cliente_arquivo_ausente(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "CLIENTES_CSV", tmp_path / "nao_existe.csv")
    assert repo.buscar_cliente("12345678901", "1990-05-14") is None


def test_carregar_tabela_score_arquivo_ausente(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "SCORE_LIMITE_CSV", tmp_path / "nao_existe.csv")
    assert repo.carregar_tabela_score() == []
