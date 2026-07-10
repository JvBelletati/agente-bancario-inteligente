import csv
import logging
from src.config import CLIENTES_CSV, SCORE_LIMITE_CSV, SOLICITACOES_CSV

logger = logging.getLogger(__name__)

_SOLIC_COLS = [
    "cpf_cliente", "data_hora_solicitacao", "limite_atual",
    "novo_limite_solicitado", "status_pedido",
]


def normalizar_cpf(cpf: str) -> str:
    return "".join(ch for ch in str(cpf) if ch.isdigit())


def _ler_clientes() -> list[dict]:
    try:
        with open(CLIENTES_CSV, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        logger.error("clientes.csv não encontrado em %s", CLIENTES_CSV)
        return []
    except OSError as e:
        logger.exception("Erro ao ler clientes.csv: %s", e)
        return []


def _to_cliente(row: dict) -> dict:
    return {
        "cpf": normalizar_cpf(row["cpf"]),
        "nome": row["nome"],
        "data_nascimento": row["data_nascimento"],
        "limite_atual": float(row["limite_atual"]),
        "score": int(row["score"]),
    }


def obter_cliente_por_cpf(cpf: str) -> dict | None:
    alvo = normalizar_cpf(cpf)
    for row in _ler_clientes():
        if normalizar_cpf(row["cpf"]) == alvo:
            return _to_cliente(row)
    return None


def buscar_cliente(cpf: str, data_nascimento: str) -> dict | None:
    c = obter_cliente_por_cpf(cpf)
    if c and c["data_nascimento"] == data_nascimento.strip():
        return c
    return None


def atualizar_score(cpf: str, novo_score: int) -> None:
    alvo = normalizar_cpf(cpf)
    rows = _ler_clientes()
    if not rows:
        raise RuntimeError("Base de clientes indisponível para atualização.")
    for row in rows:
        if normalizar_cpf(row["cpf"]) == alvo:
            row["score"] = str(int(novo_score))
    with open(CLIENTES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cpf", "nome", "data_nascimento", "limite_atual", "score"])
        w.writeheader()
        w.writerows(rows)


def carregar_tabela_score() -> list[dict]:
    with open(SCORE_LIMITE_CSV, newline="", encoding="utf-8") as f:
        return [
            {
                "score_min": int(r["score_min"]),
                "score_max": int(r["score_max"]),
                "limite_maximo": float(r["limite_maximo"]),
            }
            for r in csv.DictReader(f)
        ]


def append_solicitacao(cpf: str, limite_atual: float, novo_limite: float,
                       data_hora: str, status: str = "pendente") -> None:
    novo = not SOLICITACOES_CSV.exists()
    with open(SOLICITACOES_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_SOLIC_COLS)
        if novo:
            w.writeheader()
        w.writerow({
            "cpf_cliente": normalizar_cpf(cpf),
            "data_hora_solicitacao": data_hora,
            "limite_atual": limite_atual,
            "novo_limite_solicitado": novo_limite,
            "status_pedido": status,
        })


def atualizar_status_solicitacao(cpf: str, data_hora: str, status: str) -> None:
    if not SOLICITACOES_CSV.exists():
        return
    with open(SOLICITACOES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    alvo = normalizar_cpf(cpf)
    for row in rows:
        if row["cpf_cliente"] == alvo and row["data_hora_solicitacao"] == data_hora:
            row["status_pedido"] = status
    with open(SOLICITACOES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_SOLIC_COLS)
        w.writeheader()
        w.writerows(rows)
