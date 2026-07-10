def encerrar() -> dict:
    """Encerra o atendimento quando o cliente deseja finalizar a conversa."""
    return {"encerrar": True, "mensagem": "Foi um prazer te atender. Até logo!"}


def iniciar_entrevista_credito() -> dict:
    """Inicia a entrevista financeira para tentar reajustar o score do cliente."""
    return {"handoff": "entrevista", "mensagem": ""}


def retornar_para_credito() -> dict:
    """Retorna o atendimento ao contexto de crédito após a entrevista."""
    return {"handoff": "credito", "mensagem": ""}


def outro_assunto() -> dict:
    """Sinaliza que o cliente quer tratar de outro assunto (novo roteamento)."""
    return {"handoff": "router", "mensagem": ""}
