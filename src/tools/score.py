import unicodedata
from src.config import PESO_RENDA, PESO_EMPREGO, PESO_DEPENDENTES, PESO_DIVIDAS
from src.data.repository import atualizar_score


def _sem_acento(txt: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    ).lower().strip()


def _norm_emprego(tipo: str) -> str:
    m = {"formal": "formal", "autonomo": "autônomo", "desempregado": "desempregado"}
    chave = _sem_acento(tipo)
    if chave not in m:
        raise ValueError(f"tipo_emprego inválido: {tipo!r}")
    return m[chave]


def _norm_dividas(valor: str) -> str:
    v = _sem_acento(str(valor))
    if v in {"sim", "s", "true", "1"}:
        return "sim"
    if v in {"nao", "n", "false", "0"}:
        return "não"
    raise ValueError(f"tem_dividas inválido: {valor!r}")


def _bucket_dependentes(n: int) -> object:
    return n if n in (0, 1, 2) else "3+"


def calcular_score(renda: float, tipo_emprego: str, despesas: float,
                   num_dependentes: int, tem_dividas: str) -> int:
    try:
        renda = float(renda)
        despesas = float(despesas)
        num_dependentes = int(num_dependentes)
    except (TypeError, ValueError):
        raise ValueError("renda, despesas e num_dependentes devem ser numéricos.")
    if renda < 0 or despesas < 0 or num_dependentes < 0:
        raise ValueError("Valores não podem ser negativos.")

    emprego = _norm_emprego(tipo_emprego)
    dividas = _norm_dividas(tem_dividas)

    score = (
        (renda / (despesas + 1)) * PESO_RENDA
        + PESO_EMPREGO[emprego]
        + PESO_DEPENDENTES[_bucket_dependentes(num_dependentes)]
        + PESO_DIVIDAS[dividas]
    )
    return max(0, min(1000, round(score)))


def atualizar_score_cliente(cpf: str, renda: float, tipo_emprego: str,
                            despesas: float, num_dependentes: int,
                            tem_dividas: str) -> dict:
    """Recalcula o score a partir dos dados da entrevista e persiste na base."""
    try:
        novo = calcular_score(renda, tipo_emprego, despesas, num_dependentes, tem_dividas)
    except ValueError as e:
        return {"novo_score": None, "mensagem": f"Dados inválidos: {e}"}
    try:
        atualizar_score(cpf, novo)
    except RuntimeError:
        return {"novo_score": None, "mensagem": "Não consegui atualizar seu score agora."}
    return {"novo_score": novo, "mensagem": f"Seu novo score é {novo}."}
