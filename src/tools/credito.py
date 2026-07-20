import logging
from datetime import datetime
from src.data.repository import (
    obter_cliente_por_cpf, carregar_tabela_score,
    append_solicitacao, atualizar_status_solicitacao, mascarar_cpf,
)

logger = logging.getLogger(__name__)


def consultar_limite(cpf: str) -> dict:
    """Consulta o limite de crédito atual do cliente."""
    cliente = obter_cliente_por_cpf(cpf)
    if not cliente:
        return {"limite_atual": 0.0, "mensagem": "Não localizei os dados do cliente."}
    return {
        "limite_atual": cliente["limite_atual"],
        "mensagem": f"Seu limite atual é de R$ {cliente['limite_atual']:.2f}.",
    }


def limite_maximo_para_score(score: int, tabela: list[dict]) -> float:
    for faixa in tabela:
        if faixa["score_min"] <= score <= faixa["score_max"]:
            return faixa["limite_maximo"]
    return 0.0


def registrar_solicitacao_aumento(cpf: str, novo_limite: float) -> dict:
    """Registra um pedido formal de aumento de limite com status 'pendente'."""
    cliente = obter_cliente_por_cpf(cpf)
    limite_atual = cliente["limite_atual"] if cliente else 0.0
    data_hora = datetime.now().isoformat(timespec="seconds")
    append_solicitacao(cpf, limite_atual, float(novo_limite), data_hora, "pendente")
    logger.info(
        "[CRÉDITO] FASE 1 — solicitação REGISTRADA status=pendente | cpf=%s limite_atual=%.2f "
        "novo_limite=%.2f data_hora=%s",
        mascarar_cpf(cpf), limite_atual, float(novo_limite), data_hora,
    )
    return {
        "data_hora": data_hora,
        "limite_atual": limite_atual,
        "novo_limite": float(novo_limite),
        "status": "pendente",
        "mensagem": "Pedido registrado. Vou avaliar seu score agora.",
    }


def avaliar_score_limite(cpf: str, novo_limite: float, data_hora: str) -> dict:
    """Avalia se o novo limite é permitido para o score do cliente e atualiza o status."""
    cliente = obter_cliente_por_cpf(cpf)
    score = cliente["score"] if cliente else 0
    teto = limite_maximo_para_score(score, carregar_tabela_score())
    aprovado = float(novo_limite) <= teto
    status = "aprovado" if aprovado else "rejeitado"
    atualizar_status_solicitacao(cpf, data_hora, status)
    logger.info(
        "[CRÉDITO] FASE 2 — solicitação AVALIADA status=%s | cpf=%s score=%s teto=%.2f "
        "novo_limite=%.2f data_hora=%s",
        status, mascarar_cpf(cpf), score, teto, float(novo_limite), data_hora,
    )
    if aprovado:
        msg = f"Boa notícia! Seu pedido de R$ {float(novo_limite):.2f} foi aprovado."
    else:
        msg = (f"Seu score atual permite até R$ {teto:.2f}, então o pedido de "
               f"R$ {float(novo_limite):.2f} não pôde ser aprovado.")
    return {"status": status, "limite_maximo": teto, "mensagem": msg}
