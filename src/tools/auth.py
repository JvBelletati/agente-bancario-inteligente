from src.data.repository import buscar_cliente


def autenticar_cliente(cpf: str, data_nascimento: str) -> dict:
    """Valida CPF + data de nascimento contra a base de clientes.

    Args:
        cpf: CPF informado pelo cliente (com ou sem formatação).
        data_nascimento: data no formato AAAA-MM-DD.
    """
    cliente = buscar_cliente(cpf, data_nascimento)
    if cliente:
        return {
            "autenticado": True,
            "cliente": cliente,
            "mensagem": f"Autenticação bem-sucedida para {cliente['nome']}.",
        }
    return {
        "autenticado": False,
        "cliente": None,
        "mensagem": "Não encontrei um cliente com esse CPF e data de nascimento.",
    }
