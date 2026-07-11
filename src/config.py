import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

CLIENTES_CSV = DATA_DIR / "clientes.csv"
SCORE_LIMITE_CSV = DATA_DIR / "score_limite.csv"
SOLICITACOES_CSV = DATA_DIR / "solicitacoes_aumento_limite.csv"
LOG_FILE = LOG_DIR / "app.log"

# Modelo configurável por env: troque em .env sem mexer no código
# (ex.: GEMINI_MODEL=gemini-2.5-flash) caso o free tier de um modelo esteja indisponível.
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
# Falha rápido em erros como 429 (cota) em vez de ficar ~35s tentando de novo.
LLM_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
MAX_TENTATIVAS_AUTH = 3

PESO_RENDA = 30
PESO_EMPREGO = {"formal": 300, "autônomo": 200, "desempregado": 0}
PESO_DEPENDENTES = {0: 100, 1: 80, 2: 60, "3+": 30}
PESO_DIVIDAS = {"sim": -100, "não": 100}

# AwesomeAPI: retorna {"USDBRL": {"bid": "5.43", ...}}
CAMBIO_API_URL = "https://economia.awesomeapi.com.br/last/{par}"


def get_llm(temperature: float = 0.0):
    from langchain_google_genai import ChatGoogleGenerativeAI
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada. Copie .env.example para .env.")
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        temperature=temperature,
        google_api_key=api_key,
        max_retries=LLM_MAX_RETRIES,
    )
