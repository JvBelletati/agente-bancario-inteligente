import logging
import httpx
from src.config import CAMBIO_API_URL

logger = logging.getLogger(__name__)


def consultar_cotacao(moeda: str = "USD", moeda_destino: str = "BRL") -> dict:
    """Consulta a cotação atual de uma moeda (ex.: USD, EUR) em relação ao BRL."""
    moeda = moeda.upper().strip()
    par = f"{moeda}-{moeda_destino.upper().strip()}"
    chave = f"{moeda}{moeda_destino.upper().strip()}"
    try:
        resp = httpx.get(CAMBIO_API_URL.format(par=par), timeout=8.0)
        if resp.status_code != 200:
            logger.warning("API de câmbio retornou %s para %s", resp.status_code, par)
            return {"moeda": moeda, "valor": None,
                    "mensagem": f"Não encontrei a cotação de {moeda} agora."}
        valor = float(resp.json()[chave]["bid"])
        logger.info("[CÂMBIO] cotação obtida | par=%s valor=R$ %.2f", par, valor)
        return {"moeda": moeda, "valor": valor,
                "mensagem": f"A cotação atual de {moeda} é R$ {valor:.2f}."}
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.exception("Falha ao consultar câmbio: %s", e)
        return {"moeda": moeda, "valor": None,
                "mensagem": "Não consegui obter a cotação em tempo real agora, tente em instantes."}
