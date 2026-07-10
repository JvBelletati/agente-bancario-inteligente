# Agente Bancário Inteligente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um sistema de atendimento bancário multi-agente (Banco Ágil) onde o cliente vê um único assistente, com 4 agentes especializados orquestrados por LangGraph e UI em Streamlit.

**Architecture:** Grafo de estados LangGraph com estado compartilhado (`BankState`). Um gate determinístico força autenticação antes de qualquer especialista; um router LLM-leve direciona por intenção; cada especialista é um nó ReAct com subconjunto restrito de tools. Regras de negócio (auth, score, aprovação, I/O CSV) são funções puras/tools determinísticas — o LLM só conversa e decide *quando* chamar cada tool. Handoffs via `Command(goto=...)`, imperceptíveis ao cliente.

**Tech Stack:** Python 3.11+, LangGraph, langchain-google-genai (Gemini `gemini-2.0-flash`), Streamlit, pandas, httpx, python-dotenv, pytest.

## Global Constraints

- Python 3.11+ (usa union type `X | None`).
- LLM: `gemini-2.0-flash` via `langchain-google-genai`; chave em `GEMINI_API_KEY` (env, nunca hardcoded).
- Toda I/O de CSV passa EXCLUSIVAMENTE por `src/data/repository.py`. Nenhuma tool/nó abre CSV direto.
- CPF sempre armazenado e comparado como **11 dígitos sem formatação**; entradas do usuário são normalizadas (remover `.`/`-`/espaços) antes de comparar.
- Score sempre inteiro clampado em `[0, 1000]`.
- Colunas de `solicitacoes_aumento_limite.csv` (exatas): `cpf_cliente`, `data_hora_solicitacao`, `limite_atual`, `novo_limite_solicitado`, `status_pedido`.
- Timestamps em ISO 8601 (`datetime.now().isoformat(timespec="seconds")`).
- Máximo de 3 tentativas de autenticação; na 3ª falha, encerrar com mensagem gentil.
- Nenhum agente pode chamar tool fora do seu conjunto (garantido pela composição de tools por nó).
- Pesos de score (fixos em `config.py`): `PESO_RENDA=30`; emprego `{formal:300, autônomo:200, desempregado:0}`; dependentes `{0:100, 1:80, 2:60, "3+":30}`; dívidas `{sim:-100, não:100}`.
- Respostas ao cliente em português, tom respeitoso e objetivo, sem mensagens de "transferência".
- Commits frequentes e pequenos; mensagens de commit em inglês com prefixo convencional (`feat:`, `test:`, `chore:`, `docs:`).

---

### Task 1: Scaffold do projeto, dependências e configuração

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/__init__.py`, `src/config.py`
- Create: `tests/__init__.py`
- Create: dirs `data/`, `logs/`, `scripts/`, `src/graph/nodes/`, `src/tools/`, `src/data/`, `src/prompts/` (com `__init__.py` onde houver código Python)

**Interfaces:**
- Produces: `src/config.py` expondo constantes `DATA_DIR, CLIENTES_CSV, SCORE_LIMITE_CSV, SOLICITACOES_CSV, LOG_FILE, LLM_MODEL, MAX_TENTATIVAS_AUTH, PESO_RENDA, PESO_EMPREGO, PESO_DEPENDENTES, PESO_DIVIDAS, CAMBIO_API_URL` e função `get_llm(temperature: float = 0.0)`.

- [ ] **Step 1: Criar `requirements.txt`**

```
langgraph>=0.2.40
langchain-core>=0.3.0
langchain-google-genai>=2.0.0
streamlit>=1.30.0
pandas>=2.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

- [ ] **Step 2: Criar `.gitignore`**

```
__pycache__/
*.pyc
.env
logs/
.venv/
venv/
.pytest_cache/
data/solicitacoes_aumento_limite.csv
```

- [ ] **Step 3: Criar `.env.example`**

```
GEMINI_API_KEY=sua_chave_aqui
```

- [ ] **Step 4: Criar `src/config.py`**

```python
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

LLM_MODEL = "gemini-2.0-flash"
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
    return ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=temperature, google_api_key=api_key)
```

- [ ] **Step 5: Criar arquivos `__init__.py` vazios**

Criar: `src/__init__.py`, `src/graph/__init__.py`, `src/graph/nodes/__init__.py`, `src/tools/__init__.py`, `src/data/__init__.py`, `tests/__init__.py`. Criar `logs/.gitkeep`.

- [ ] **Step 6: Instalar dependências e verificar import**

Run: `pip install -r requirements.txt && python -c "import langgraph, streamlit, pandas, httpx; print('ok')"`
Expected: imprime `ok`

- [ ] **Step 7: Commit**

```bash
git init
git add .
git commit -m "chore: project scaffold, config and dependencies"
```

---

### Task 2: Dados sintéticos (seed) e tabela de score

**Files:**
- Create: `scripts/seed_data.py`
- Create: `data/clientes.csv` (gerado)
- Create: `data/score_limite.csv` (gerado)

**Interfaces:**
- Produces: `data/clientes.csv` (colunas `cpf,nome,data_nascimento,limite_atual,score`) e `data/score_limite.csv` (colunas `score_min,score_max,limite_maximo`). `scripts/seed_data.py` regenera ambos ao rodar `python scripts/seed_data.py`.

- [ ] **Step 1: Criar `scripts/seed_data.py`**

```python
"""Gera os CSVs base (clientes e tabela de score→limite)."""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CLIENTES = [
    ("12345678901", "Ana Souza",      "1990-05-14",  2000.00, 620),
    ("23456789012", "Bruno Lima",     "1985-11-02",  5000.00, 710),
    ("34567890123", "Carla Dias",     "1998-03-27",  1000.00, 280),
    ("45678901234", "Diego Alves",    "1979-07-19", 15000.00, 865),
    ("56789012345", "Elaine Rocha",   "1993-09-08",  3000.00, 540),
    ("67890123456", "Felipe Nunes",   "2000-01-30",   800.00, 150),
    ("78901234567", "Gabriela Mota",  "1988-12-12",  8000.00, 780),
    ("89012345678", "Henrique Pires", "1995-06-05",  2500.00, 460),
    ("90123456789", "Isabela Cruz",   "1982-04-22", 12000.00, 830),
    ("01234567890", "João Reis",      "1975-08-17",   500.00, 390),
]

SCORE_LIMITE = [
    (0,   299,   500.00),
    (300, 499,  2000.00),
    (500, 699,  5000.00),
    (700, 849, 15000.00),
    (850, 1000, 50000.00),
]


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "clientes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cpf", "nome", "data_nascimento", "limite_atual", "score"])
        w.writerows(CLIENTES)
    with open(DATA_DIR / "score_limite.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score_min", "score_max", "limite_maximo"])
        w.writerows(SCORE_LIMITE)
    print(f"Gerados {len(CLIENTES)} clientes e {len(SCORE_LIMITE)} faixas de score.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar o seed**

Run: `python scripts/seed_data.py`
Expected: `Gerados 10 clientes e 5 faixas de score.` e arquivos criados em `data/`.

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_data.py data/clientes.csv data/score_limite.csv
git commit -m "feat: seed synthetic clients and score-limit table"
```

---

### Task 3: Camada de repositório (I/O de CSV) — TDD

**Files:**
- Create: `src/data/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Consumes: `src/config.py` (paths).
- Produces:
  - `normalizar_cpf(cpf: str) -> str`
  - `buscar_cliente(cpf: str, data_nascimento: str) -> dict | None`
  - `obter_cliente_por_cpf(cpf: str) -> dict | None`
  - `atualizar_score(cpf: str, novo_score: int) -> None`
  - `carregar_tabela_score() -> list[dict]` (cada dict: `{"score_min": int, "score_max": int, "limite_maximo": float}`)
  - `append_solicitacao(cpf: str, limite_atual: float, novo_limite: float, data_hora: str, status: str = "pendente") -> None`
  - `atualizar_status_solicitacao(cpf: str, data_hora: str, status: str) -> None`
  - Cliente dict: `{"cpf": str, "nome": str, "data_nascimento": str, "limite_atual": float, "score": int}`.

- [ ] **Step 1: Escrever teste que falha (`tests/test_repository.py`)**

```python
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
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `pytest tests/test_repository.py -v`
Expected: FAIL (`ModuleNotFoundError` / `AttributeError: normalizar_cpf`).

- [ ] **Step 3: Implementar `src/data/repository.py`**

```python
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
```

Nota: o teste faz `monkeypatch.setattr(repo, "CLIENTES_CSV", ...)`, por isso os paths são importados como nomes de módulo (referenciáveis via `repo.CLIENTES_CSV`).

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_repository.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add src/data/repository.py tests/test_repository.py
git commit -m "feat: CSV repository layer with tests"
```

---

### Task 4: Fórmula de score (função pura) — TDD

**Files:**
- Create: `src/tools/score.py` (só a função pura nesta task)
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: `src/config.py` (pesos).
- Produces: `calcular_score(renda: float, tipo_emprego: str, despesas: float, num_dependentes: int, tem_dividas: str) -> int`. Retorna inteiro em `[0, 1000]`. Lança `ValueError` para entradas negativas/não-numéricas.

- [ ] **Step 1: Escrever teste que falha (`tests/test_score.py`)**

```python
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
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `pytest tests/test_score.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `calcular_score` em `src/tools/score.py`**

```python
import unicodedata
from src.config import PESO_RENDA, PESO_EMPREGO, PESO_DEPENDENTES, PESO_DIVIDAS


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
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_score.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/score.py tests/test_score.py
git commit -m "feat: pure credit-score formula with tests"
```

---

### Task 5: Tool de autenticação — TDD

**Files:**
- Create: `src/tools/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `src/data/repository.py` (`buscar_cliente`).
- Produces: `autenticar_cliente(cpf: str, data_nascimento: str) -> dict` retornando `{"autenticado": bool, "cliente": dict | None, "mensagem": str}`. Função pura (não conta tentativas — isso é responsabilidade do nó Triagem).

- [ ] **Step 1: Escrever teste que falha (`tests/test_auth.py`)**

```python
from unittest.mock import patch
from src.tools.auth import autenticar_cliente

CLIENTE = {"cpf": "12345678901", "nome": "Ana Souza",
           "data_nascimento": "1990-05-14", "limite_atual": 2000.0, "score": 620}


def test_auth_sucesso():
    with patch("src.tools.auth.buscar_cliente", return_value=CLIENTE):
        r = autenticar_cliente("123.456.789-01", "1990-05-14")
    assert r["autenticado"] is True
    assert r["cliente"]["nome"] == "Ana Souza"


def test_auth_falha_retorna_cliente_none():
    with patch("src.tools.auth.buscar_cliente", return_value=None):
        r = autenticar_cliente("00000000000", "2000-01-01")
    assert r["autenticado"] is False
    assert r["cliente"] is None
    assert isinstance(r["mensagem"], str)
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/tools/auth.py`**

```python
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
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_auth.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/auth.py tests/test_auth.py
git commit -m "feat: authentication tool with tests"
```

---

### Task 6: Tools de crédito (consulta, solicitação, avaliação) — TDD

**Files:**
- Create: `src/tools/credito.py`
- Test: `tests/test_credito.py`

**Interfaces:**
- Consumes: `src/data/repository.py` (`obter_cliente_por_cpf`, `carregar_tabela_score`, `append_solicitacao`, `atualizar_status_solicitacao`).
- Produces:
  - `consultar_limite(cpf: str) -> dict` → `{"limite_atual": float, "mensagem": str}`
  - `limite_maximo_para_score(score: int, tabela: list[dict]) -> float`
  - `registrar_solicitacao_aumento(cpf: str, novo_limite: float) -> dict` → `{"data_hora": str, "limite_atual": float, "novo_limite": float, "status": "pendente", "mensagem": str}`
  - `avaliar_score_limite(cpf: str, novo_limite: float, data_hora: str) -> dict` → `{"status": "aprovado"|"rejeitado", "limite_maximo": float, "mensagem": str}`

- [ ] **Step 1: Escrever teste que falha (`tests/test_credito.py`)**

```python
from unittest.mock import patch
import src.tools.credito as credito

TABELA = [
    {"score_min": 0, "score_max": 299, "limite_maximo": 500.0},
    {"score_min": 500, "score_max": 699, "limite_maximo": 5000.0},
    {"score_min": 700, "score_max": 849, "limite_maximo": 15000.0},
]
CLIENTE = {"cpf": "12345678901", "nome": "Ana", "data_nascimento": "1990-05-14",
           "limite_atual": 2000.0, "score": 620}


def test_limite_maximo_para_score_borda_inferior():
    assert credito.limite_maximo_para_score(500, TABELA) == 5000.0


def test_limite_maximo_para_score_borda_superior():
    assert credito.limite_maximo_para_score(699, TABELA) == 5000.0


def test_limite_maximo_para_score_fora_da_tabela_retorna_zero():
    assert credito.limite_maximo_para_score(999, TABELA) == 0.0


def test_consultar_limite():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE):
        r = credito.consultar_limite("12345678901")
    assert r["limite_atual"] == 2000.0


def test_registrar_solicitacao_status_pendente():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE), \
         patch("src.tools.credito.append_solicitacao") as ap:
        r = credito.registrar_solicitacao_aumento("12345678901", 4000.0)
    assert r["status"] == "pendente"
    assert r["limite_atual"] == 2000.0
    ap.assert_called_once()


def test_avaliar_aprovado_quando_dentro_do_teto():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE), \
         patch("src.tools.credito.carregar_tabela_score", return_value=TABELA), \
         patch("src.tools.credito.atualizar_status_solicitacao") as upd:
        r = credito.avaliar_score_limite("12345678901", 4000.0, "2026-07-10T10:00:00")
    assert r["status"] == "aprovado"  # score 620 -> teto 5000 >= 4000
    upd.assert_called_once_with("12345678901", "2026-07-10T10:00:00", "aprovado")


def test_avaliar_rejeitado_quando_acima_do_teto():
    with patch("src.tools.credito.obter_cliente_por_cpf", return_value=CLIENTE), \
         patch("src.tools.credito.carregar_tabela_score", return_value=TABELA), \
         patch("src.tools.credito.atualizar_status_solicitacao"):
        r = credito.avaliar_score_limite("12345678901", 9000.0, "2026-07-10T10:00:00")
    assert r["status"] == "rejeitado"  # teto 5000 < 9000
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `pytest tests/test_credito.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `src/tools/credito.py`**

```python
from datetime import datetime
from src.data.repository import (
    obter_cliente_por_cpf, carregar_tabela_score,
    append_solicitacao, atualizar_status_solicitacao,
)


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
    if aprovado:
        msg = f"Boa notícia! Seu pedido de R$ {float(novo_limite):.2f} foi aprovado."
    else:
        msg = (f"Seu score atual permite até R$ {teto:.2f}, então o pedido de "
               f"R$ {float(novo_limite):.2f} não pôde ser aprovado.")
    return {"status": status, "limite_maximo": teto, "mensagem": msg}
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_credito.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/credito.py tests/test_credito.py
git commit -m "feat: credit tools (query, request, evaluation) with tests"
```

---

### Task 7: Tool de atualização de score (Entrevista) — TDD

**Files:**
- Modify: `src/tools/score.py` (adicionar `atualizar_score_cliente`)
- Test: `tests/test_score_update.py`

**Interfaces:**
- Consumes: `calcular_score` (mesmo módulo), `src/data/repository.py` (`atualizar_score`).
- Produces: `atualizar_score_cliente(cpf: str, renda: float, tipo_emprego: str, despesas: float, num_dependentes: int, tem_dividas: str) -> dict` → `{"novo_score": int, "mensagem": str}`. Em erro de entrada, retorna `{"novo_score": None, "mensagem": <erro amigável>}`.

- [ ] **Step 1: Escrever teste que falha (`tests/test_score_update.py`)**

```python
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
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `pytest tests/test_score_update.py -v`
Expected: FAIL (`ImportError: cannot import name 'atualizar_score_cliente'`).

- [ ] **Step 3: Adicionar em `src/tools/score.py` (topo: novo import; fim: nova função)**

No topo do arquivo, adicionar o import:

```python
from src.data.repository import atualizar_score
```

No fim do arquivo, adicionar:

```python
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
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_score_update.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/score.py tests/test_score_update.py
git commit -m "feat: score update tool for interview agent"
```

---

### Task 8: Tool de câmbio (API externa) — TDD com mock

**Files:**
- Create: `src/tools/cambio.py`
- Test: `tests/test_cambio.py`

**Interfaces:**
- Consumes: `src/config.py` (`CAMBIO_API_URL`), `httpx`.
- Produces: `consultar_cotacao(moeda: str = "USD", moeda_destino: str = "BRL") -> dict` → `{"moeda": str, "valor": float | None, "mensagem": str}`. Trata timeout, status != 200 e erro de rede sem levantar exceção.

- [ ] **Step 1: Escrever teste que falha (`tests/test_cambio.py`)**

```python
from unittest.mock import patch, MagicMock
import httpx
from src.tools.cambio import consultar_cotacao


def _resp(json_data, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data
    return m


def test_cotacao_sucesso():
    payload = {"USDBRL": {"bid": "5.43", "name": "Dólar Americano/Real Brasileiro"}}
    with patch("src.tools.cambio.httpx.get", return_value=_resp(payload)):
        r = consultar_cotacao("USD")
    assert r["valor"] == 5.43
    assert "5.43" in r["mensagem"]


def test_cotacao_status_erro():
    with patch("src.tools.cambio.httpx.get", return_value=_resp({}, status=404)):
        r = consultar_cotacao("XXX")
    assert r["valor"] is None
    assert isinstance(r["mensagem"], str)


def test_cotacao_timeout_nao_quebra():
    with patch("src.tools.cambio.httpx.get", side_effect=httpx.TimeoutException("t")):
        r = consultar_cotacao("USD")
    assert r["valor"] is None
    assert "não" in r["mensagem"].lower() or "instab" in r["mensagem"].lower()
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `pytest tests/test_cambio.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/tools/cambio.py`**

```python
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
        return {"moeda": moeda, "valor": valor,
                "mensagem": f"A cotação atual de {moeda} é R$ {valor:.2f}."}
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.exception("Falha ao consultar câmbio: %s", e)
        return {"moeda": moeda, "valor": None,
                "mensagem": "Não consegui obter a cotação em tempo real agora, tente em instantes."}
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_cambio.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/cambio.py tests/test_cambio.py
git commit -m "feat: currency-quote tool with error handling and tests"
```

---

### Task 9: Estado, tools de controle e runtime dos agentes

**Files:**
- Create: `src/graph/state.py`
- Create: `src/tools/common.py`
- Create: `src/graph/agent_runtime.py`
- Test: `tests/test_agent_runtime.py`

**Interfaces:**
- Consumes: `src/config.py` (`get_llm`).
- Produces:
  - `BankState` (TypedDict, ver abaixo).
  - `encerrar() -> dict` → `{"encerrar": True, "mensagem": str}`
  - `iniciar_entrevista_credito() -> dict` → `{"handoff": "entrevista", "mensagem": str}`
  - `retornar_para_credito() -> dict` → `{"handoff": "credito", "mensagem": str}`
  - `outro_assunto() -> dict` → `{"handoff": "router", "mensagem": str}`
  - `as_tool(fn) -> StructuredTool` (wrapper p/ bind_tools)
  - `run_react_turn(state, system_prompt, funcs, max_iters=6) -> tuple[list, list]` retornando `(novas_mensagens, resultados)` onde `resultados` é `list[dict]` (os dicts retornados pelas tools chamadas neste turno, na ordem).

- [ ] **Step 1: Criar `src/graph/state.py`**

```python
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class BankState(TypedDict):
    messages: Annotated[list, add_messages]
    autenticado: bool
    tentativas_auth: int
    cpf: str | None
    cliente: dict | None
    active_agent: str
    ultima_solicitacao: dict | None
    dados_entrevista: dict | None
    encerrar: bool
```

- [ ] **Step 2: Criar `src/tools/common.py`**

```python
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
```

- [ ] **Step 3: Criar `src/graph/agent_runtime.py`**

```python
import logging
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from src.config import get_llm

logger = logging.getLogger(__name__)


def as_tool(fn) -> StructuredTool:
    return StructuredTool.from_function(fn)


def run_react_turn(state, system_prompt: str, funcs: list, max_iters: int = 6):
    """Executa um turno ReAct limitado para um nó.

    funcs: lista de funções Python (plain) que este agente pode chamar.
    Retorna (novas_mensagens, resultados):
      - novas_mensagens: AIMessage/ToolMessage geradas neste turno (p/ add_messages)
      - resultados: dicts retornados pelas tools chamadas (o nó pós-processa em estado/goto)
    """
    by_name = {f.__name__: f for f in funcs}
    tools = [as_tool(f) for f in funcs]
    llm = get_llm().bind_tools(tools) if tools else get_llm()

    conversa = [SystemMessage(content=system_prompt), *state["messages"]]
    novas = []
    resultados = []

    for _ in range(max_iters):
        ai = llm.invoke(conversa)
        conversa.append(ai)
        novas.append(ai)
        if not getattr(ai, "tool_calls", None):
            return novas, resultados
        for call in ai.tool_calls:
            fn = by_name.get(call["name"])
            if fn is None:
                out = {"mensagem": f"Ação {call['name']} indisponível."}
            else:
                try:
                    out = fn(**call["args"])
                except Exception as e:  # falha graciosa
                    logger.exception("Erro na tool %s: %s", call["name"], e)
                    out = {"mensagem": "Tive um problema ao executar essa ação."}
            resultados.append({"name": call["name"], "args": call["args"], "out": out})
            tm = ToolMessage(content=str(out.get("mensagem", out)), tool_call_id=call["id"])
            conversa.append(tm)
            novas.append(tm)
    return novas, resultados
```

- [ ] **Step 4: Escrever teste do runtime (`tests/test_agent_runtime.py`)**

Usa um LLM fake que devolve mensagens pré-scriptadas (uma com tool_call, depois uma final).

```python
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage
from src.graph import agent_runtime


def _ai_com_toolcall(nome, args):
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args, "id": "call_1"}])


def _ai_final(texto):
    return AIMessage(content=texto)


def test_run_react_turn_executa_tool_e_coleta_resultado():
    def minha_tool(x: int) -> dict:
        """soma 1"""
        return {"valor": x + 1, "mensagem": f"resultado {x+1}"}

    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    fake_llm.invoke.side_effect = [_ai_com_toolcall("minha_tool", {"x": 4}), _ai_final("pronto")]

    state = {"messages": [HumanMessage(content="oi")]}
    with patch("src.graph.agent_runtime.get_llm", return_value=fake_llm):
        novas, resultados = agent_runtime.run_react_turn(state, "system", [minha_tool])

    assert resultados[0]["out"]["valor"] == 5
    assert novas[-1].content == "pronto"
```

- [ ] **Step 5: Rodar testes**

Run: `pytest tests/test_agent_runtime.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/graph/state.py src/tools/common.py src/graph/agent_runtime.py tests/test_agent_runtime.py
git commit -m "feat: shared state, control tools and ReAct runtime"
```

---

### Task 10: Prompts e nós Triagem + gate de autenticação

**Files:**
- Create: `src/prompts/personas.py`
- Create: `src/graph/nodes/triagem.py`
- Create: `src/graph/router.py` (só `gate_auth` nesta task)

**Interfaces:**
- Consumes: `run_react_turn`, `autenticar_cliente`, `encerrar`, `BankState`, `MAX_TENTATIVAS_AUTH`.
- Produces:
  - `PERSONA_BASE: str` (cabeçalho comum a todos os prompts).
  - `gate_auth(state: BankState) -> Command` — roteia START.
  - `triagem_node(state: BankState) -> Command` — nó de autenticação.

- [ ] **Step 1: Criar `src/prompts/personas.py`**

```python
PERSONA_BASE = (
    "Você é o assistente virtual do Banco Ágil, um banco digital. "
    "Fale sempre em português do Brasil, com tom cordial, respeitoso e objetivo. "
    "Nunca revele que existem múltiplos agentes internos nem mencione 'transferência' "
    "ou 'redirecionamento'; para o cliente, você é um único assistente. "
    "Evite repetições desnecessárias e não invente informações."
)

PROMPT_TRIAGEM = PERSONA_BASE + (
    "\n\nSua tarefa AGORA é autenticar o cliente antes de qualquer outro assunto. "
    "Cumprimente (se ainda não cumprimentou) e peça o CPF e a data de nascimento "
    "(formato AAAA-MM-DD). Quando tiver AMBOS, chame a tool `autenticar_cliente`. "
    "Não peça os dois de uma vez de forma robótica; conduza de forma natural. "
    "Se o cliente pedir para encerrar, chame `encerrar`. "
    "Não prometa serviços antes da autenticação."
)

PROMPT_ROUTER = (
    "Classifique a intenção do cliente na última mensagem em um destino de atendimento. "
    "Responda SOMENTE com o destino."
)

PROMPT_CREDITO = PERSONA_BASE + (
    "\n\nVocê agora cuida de crédito. O cliente JÁ está autenticado. "
    "Você pode: consultar o limite atual (`consultar_limite`) e processar pedidos de "
    "aumento de limite. Para um aumento: quando o cliente informar o novo valor desejado, "
    "chame `registrar_solicitacao_aumento` e, em seguida, `avaliar_score_limite` usando a "
    "`data_hora` retornada. Comunique o resultado (aprovado/rejeitado) com clareza. "
    "Se for REJEITADO, ofereça de forma acolhedora uma entrevista financeira que pode "
    "reajustar o score; se o cliente aceitar, chame `iniciar_entrevista_credito`. "
    "Se o cliente quiser outro assunto (ex.: câmbio), chame `outro_assunto`. "
    "Se quiser encerrar, chame `encerrar`. Use o CPF do cliente disponível no contexto."
)

PROMPT_ENTREVISTA = PERSONA_BASE + (
    "\n\nConduza uma breve entrevista financeira, UMA pergunta por vez, coletando: "
    "renda mensal, tipo de emprego (formal, autônomo ou desempregado), despesas fixas "
    "mensais, número de dependentes e se possui dívidas ativas (sim/não). "
    "Quando tiver TODOS os dados, chame `atualizar_score_cliente` com eles. "
    "Depois de atualizar, informe o novo score de forma breve e chame "
    "`retornar_para_credito` para dar sequência à análise. Não peça dados repetidos."
)

PROMPT_CAMBIO = PERSONA_BASE + (
    "\n\nVocê agora cuida de câmbio. Pergunte qual moeda o cliente deseja (padrão dólar/USD) "
    "e chame `consultar_cotacao`. Apresente a cotação de forma amigável. "
    "Se o cliente quiser outro assunto, chame `outro_assunto`; se quiser encerrar, `encerrar`."
)
```

- [ ] **Step 2: Criar `src/graph/router.py` com `gate_auth`**

```python
from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from src.graph.state import BankState


def gate_auth(state: BankState) -> Command[Literal["triagem", "router", "credito", "entrevista", "cambio"]]:
    if state.get("encerrar"):
        return Command(goto=END)
    if not state.get("autenticado"):
        return Command(goto="triagem")
    ativo = state.get("active_agent")
    if ativo in ("credito", "entrevista", "cambio"):
        return Command(goto=ativo)
    return Command(goto="router")
```

- [ ] **Step 3: Criar `src/graph/nodes/triagem.py`**

```python
from langgraph.graph import END
from langgraph.types import Command
from src.config import MAX_TENTATIVAS_AUTH
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_TRIAGEM
from src.tools.auth import autenticar_cliente
from src.tools.common import encerrar


def triagem_node(state: BankState) -> Command:
    novas, resultados = run_react_turn(state, PROMPT_TRIAGEM, [autenticar_cliente, encerrar])
    update = {"messages": novas}

    for r in resultados:
        if r["name"] == "encerrar":
            return Command(goto=END, update={**update, "encerrar": True})
        if r["name"] == "autenticar_cliente":
            out = r["out"]
            if out.get("autenticado"):
                update.update({
                    "autenticado": True,
                    "cpf": out["cliente"]["cpf"],
                    "cliente": out["cliente"],
                    "active_agent": "",
                })
                return Command(goto=END, update=update)  # saúda e aguarda o pedido (router entra no próximo turno via gate_auth)
            # falha de autenticação
            tentativas = state.get("tentativas_auth", 0) + 1
            update["tentativas_auth"] = tentativas
            if tentativas >= MAX_TENTATIVAS_AUTH:
                from langchain_core.messages import AIMessage
                despedida = AIMessage(content=(
                    "Infelizmente não consegui confirmar seus dados após algumas tentativas. "
                    "Por segurança, vou encerrar por aqui. Você pode tentar novamente mais tarde. "
                    "Tenha um ótimo dia!"))
                update["messages"] = novas + [despedida]
                update["encerrar"] = True
                return Command(goto=END, update=update)
            return Command(goto=END, update=update)  # aguarda nova tentativa do cliente

    # sem tool call → pediu os dados e aguarda a resposta do cliente
    return Command(goto=END, update=update)
```

- [ ] **Step 4: Verificação manual leve (import + tipos)**

Run: `python -c "from src.graph.nodes.triagem import triagem_node; from src.graph.router import gate_auth; print('ok')"`
Expected: `ok` (sem erros de import). O comportamento conversacional será validado no smoke test (Task 14) e manualmente na UI (Task 15).

- [ ] **Step 5: Commit**

```bash
git add src/prompts/personas.py src/graph/router.py src/graph/nodes/triagem.py
git commit -m "feat: personas, auth gate and triage node"
```

---

### Task 11: Router (classificador) + nó de Crédito

**Files:**
- Modify: `src/graph/router.py` (adicionar `router_node`)
- Create: `src/graph/nodes/credito.py`

**Interfaces:**
- Consumes: `get_llm`, `run_react_turn`, tools de crédito, `PROMPT_CREDITO`.
- Produces:
  - `router_node(state: BankState) -> Command` — define `active_agent` (`credito`|`cambio`) e roteia.
  - `credito_node(state: BankState) -> Command`.

- [ ] **Step 1: Adicionar `router_node` em `src/graph/router.py`**

```python
from typing import Literal
from pydantic import BaseModel
from src.config import get_llm
from src.prompts.personas import PROMPT_ROUTER


class _Rota(BaseModel):
    destino: Literal["credito", "cambio"]


def router_node(state: BankState) -> Command[Literal["credito", "cambio"]]:
    from langchain_core.messages import SystemMessage
    llm = get_llm().with_structured_output(_Rota)
    try:
        rota = llm.invoke([SystemMessage(content=PROMPT_ROUTER), *state["messages"]])
        destino = rota.destino
    except Exception:
        destino = "credito"  # fallback seguro
    return Command(goto=destino, update={"active_agent": destino})
```

(Adicionar no topo do arquivo, junto aos imports existentes: `from typing import Literal`, `from pydantic import BaseModel`, `from src.config import get_llm`, `from src.prompts.personas import PROMPT_ROUTER`.)

- [ ] **Step 2: Criar `src/graph/nodes/credito.py`**

```python
from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_CREDITO
from src.tools.credito import (
    consultar_limite, registrar_solicitacao_aumento, avaliar_score_limite,
)
from src.tools.common import iniciar_entrevista_credito, outro_assunto, encerrar


def credito_node(state: BankState) -> Command[Literal["entrevista", "router"]]:
    cpf = state.get("cpf")

    def _consultar_limite() -> dict:
        """Consulta o limite de crédito atual do cliente autenticado."""
        return consultar_limite(cpf)

    def _registrar_solicitacao_aumento(novo_limite: float) -> dict:
        """Registra um pedido de aumento de limite (status pendente)."""
        return registrar_solicitacao_aumento(cpf, novo_limite)

    def _avaliar_score_limite(novo_limite: float, data_hora: str) -> dict:
        """Avalia o pedido de aumento contra o score do cliente."""
        return avaliar_score_limite(cpf, novo_limite, data_hora)

    funcs = [_consultar_limite, _registrar_solicitacao_aumento, _avaliar_score_limite,
             iniciar_entrevista_credito, outro_assunto, encerrar]
    novas, resultados = run_react_turn(state, PROMPT_CREDITO, funcs)
    update = {"messages": novas}

    for r in resultados:
        out = r["out"]
        if r["name"] == "_registrar_solicitacao_aumento":
            update["ultima_solicitacao"] = out
        if r["name"] == "encerrar":
            return Command(goto=END, update={**update, "encerrar": True})
        if out.get("handoff") == "entrevista":
            return Command(goto="entrevista", update={**update, "active_agent": "entrevista"})
        if out.get("handoff") == "router":
            return Command(goto="router", update={**update, "active_agent": ""})

    return Command(goto=END, update=update)  # respondeu e aguarda o cliente (fica sticky via gate_auth)
```

Nota: as tools são fechadas sobre o `cpf` do estado (o LLM não precisa nem pode informar CPF de terceiros → escopo seguro). Os nomes começam com `_` mas `StructuredTool.from_function` usa `fn.__name__`, então o LLM vê `_consultar_limite` etc. — coerente com o `by_name` do runtime.

- [ ] **Step 3: Verificação de import**

Run: `python -c "from src.graph.router import router_node; from src.graph.nodes.credito import credito_node; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add src/graph/router.py src/graph/nodes/credito.py
git commit -m "feat: intent router and credit node"
```

---

### Task 12: Nó de Entrevista de Crédito

**Files:**
- Create: `src/graph/nodes/entrevista.py`

**Interfaces:**
- Consumes: `run_react_turn`, `atualizar_score_cliente`, `retornar_para_credito`, `PROMPT_ENTREVISTA`.
- Produces: `entrevista_node(state: BankState) -> Command`. Ao retornar para crédito, se houver `ultima_solicitacao` pendente, o nó de Crédito reavaliará automaticamente na sequência (o LLM de Crédito é instruído a re-avaliar). Para garantir a re-análise determinística, este nó marca `active_agent="credito"` e adiciona uma nota de sistema curta ao histórico.

- [ ] **Step 1: Criar `src/graph/nodes/entrevista.py`**

```python
from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from langchain_core.messages import AIMessage
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_ENTREVISTA
from src.tools.score import atualizar_score_cliente
from src.tools.common import retornar_para_credito


def entrevista_node(state: BankState) -> Command[Literal["credito"]]:
    cpf = state.get("cpf")

    def _atualizar_score_cliente(renda: float, tipo_emprego: str, despesas: float,
                                 num_dependentes: int, tem_dividas: str) -> dict:
        """Recalcula e persiste o score com os dados coletados na entrevista."""
        return atualizar_score_cliente(cpf, renda, tipo_emprego, despesas,
                                       num_dependentes, tem_dividas)

    funcs = [_atualizar_score_cliente, retornar_para_credito]
    novas, resultados = run_react_turn(state, PROMPT_ENTREVISTA, funcs)
    update = {"messages": novas}
    novo_score = None

    for r in resultados:
        if r["name"] == "_atualizar_score_cliente" and r["out"].get("novo_score") is not None:
            novo_score = r["out"]["novo_score"]
            # atualiza cliente em memória p/ o Crédito reavaliar com o score novo
            cliente = dict(state.get("cliente") or {})
            cliente["score"] = novo_score
            update["cliente"] = cliente
        if r["out"].get("handoff") == "credito":
            nota = AIMessage(content="Com seu score atualizado, vou reanalisar seu pedido de limite.")
            update["messages"] = novas + [nota]
            return Command(goto="credito", update={**update, "active_agent": "credito"})

    return Command(goto=END, update=update)  # continua a entrevista no próximo turno (sticky via gate_auth)
```

- [ ] **Step 2: Verificação de import**

Run: `python -c "from src.graph.nodes.entrevista import entrevista_node; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/graph/nodes/entrevista.py
git commit -m "feat: credit interview node with score recompute"
```

---

### Task 13: Nó de Câmbio

**Files:**
- Create: `src/graph/nodes/cambio.py`

**Interfaces:**
- Consumes: `run_react_turn`, `consultar_cotacao`, `outro_assunto`, `encerrar`, `PROMPT_CAMBIO`.
- Produces: `cambio_node(state: BankState) -> Command`.

- [ ] **Step 1: Criar `src/graph/nodes/cambio.py`**

```python
from typing import Literal
from langgraph.graph import END
from langgraph.types import Command
from src.graph.state import BankState
from src.graph.agent_runtime import run_react_turn
from src.prompts.personas import PROMPT_CAMBIO
from src.tools.cambio import consultar_cotacao
from src.tools.common import outro_assunto, encerrar


def cambio_node(state: BankState) -> Command[Literal["router"]]:
    novas, resultados = run_react_turn(state, PROMPT_CAMBIO, [consultar_cotacao, outro_assunto, encerrar])
    update = {"messages": novas}
    for r in resultados:
        if r["name"] == "encerrar":
            return Command(goto=END, update={**update, "encerrar": True})
        if r["out"].get("handoff") == "router":
            return Command(goto="router", update={**update, "active_agent": ""})
    return Command(goto=END, update=update)  # respondeu e aguarda o cliente (sticky via gate_auth)
```

- [ ] **Step 2: Verificação de import**

Run: `python -c "from src.graph.nodes.cambio import cambio_node; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/graph/nodes/cambio.py
git commit -m "feat: currency exchange node"
```

---

### Task 14: Montagem do grafo + checkpointer + smoke test de integração

**Files:**
- Create: `src/graph/builder.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: todos os nós, `BankState`, `MemorySaver`.
- Produces:
  - `build_graph()` → grafo compilado com checkpointer `MemorySaver`.
  - `estado_inicial() -> dict` — valores default de `BankState`.

- [ ] **Step 1: Criar `src/graph/builder.py`**

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from src.graph.state import BankState
from src.graph.router import gate_auth, router_node
from src.graph.nodes.triagem import triagem_node
from src.graph.nodes.credito import credito_node
from src.graph.nodes.entrevista import entrevista_node
from src.graph.nodes.cambio import cambio_node


def estado_inicial() -> dict:
    return {
        "messages": [],
        "autenticado": False,
        "tentativas_auth": 0,
        "cpf": None,
        "cliente": None,
        "active_agent": "",
        "ultima_solicitacao": None,
        "dados_entrevista": None,
        "encerrar": False,
    }


def build_graph():
    g = StateGraph(BankState)
    g.add_node("gate_auth", gate_auth)
    g.add_node("triagem", triagem_node)
    g.add_node("router", router_node)
    g.add_node("credito", credito_node)
    g.add_node("entrevista", entrevista_node)
    g.add_node("cambio", cambio_node)
    g.add_edge(START, "gate_auth")
    # demais arestas são dinâmicas via Command(goto=...)
    return g.compile(checkpointer=MemorySaver())
```

Nota: como os nós retornam `Command(goto=...)`, não é necessário `add_conditional_edges`; o roteamento é carregado pelos próprios `Command`. Cada nó só precisa estar registrado com `add_node`.

- [ ] **Step 2: Escrever smoke test de integração (`tests/test_graph.py`)**

Valida DETERMINISTICAMENTE o gate de autenticação com um LLM fake que dispara `autenticar_cliente`.

```python
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage
from src.graph.builder import build_graph, estado_inicial

CLIENTE = {"cpf": "12345678901", "nome": "Ana Souza",
           "data_nascimento": "1990-05-14", "limite_atual": 2000.0, "score": 620}


def test_gate_forca_triagem_e_autentica():
    # gate_auth (não autenticado) -> triagem -> autenticar_cliente (ok) -> saudação -> END.
    # O router só entra no PRÓXIMO turno; aqui provamos o gate + a autenticação determinística.
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    fake_llm.invoke.side_effect = [
        AIMessage(content="", tool_calls=[{"name": "autenticar_cliente",
                 "args": {"cpf": "12345678901", "data_nascimento": "1990-05-14"}, "id": "c1"}]),
        AIMessage(content="Perfeito, Ana! Em que posso ajudar?"),
    ]

    with patch("src.graph.agent_runtime.get_llm", return_value=fake_llm), \
         patch("src.tools.auth.buscar_cliente", return_value=CLIENTE):
        graph = build_graph()
        estado = estado_inicial()
        estado["messages"] = [HumanMessage(content="Meu CPF é 123.456.789-01, nasci 1990-05-14")]
        cfg = {"configurable": {"thread_id": "t1"}}
        final = graph.invoke(estado, cfg)

    assert final["autenticado"] is True
    assert final["cpf"] == "12345678901"
    assert final["active_agent"] == ""  # aguarda o pedido do cliente; router entra no próximo turno
```

Nota: se a orquestração via grafo ficar frágil com o fake, simplificar para invocar `triagem_node` isolado e asseverar `update["autenticado"] is True`. O objetivo é provar o gate determinístico + auth, não o LLM.

- [ ] **Step 3: Rodar smoke test**

Run: `pytest tests/test_graph.py -v`
Expected: PASS.

- [ ] **Step 4: Rodar a suíte completa**

Run: `pytest -v`
Expected: todos os testes PASS.

- [ ] **Step 5: Commit**

```bash
git add src/graph/builder.py tests/test_graph.py
git commit -m "feat: compile agent graph with checkpointer and integration smoke test"
```

---

### Task 15: UI Streamlit + verificação manual ponta-a-ponta

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `build_graph`, `estado_inicial`.
- Produces: app Streamlit executável com `streamlit run app.py`.

- [ ] **Step 1: Criar `app.py`**

```python
import logging
import uuid
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from src.config import LOG_FILE, LOG_DIR
from src.graph.builder import build_graph, estado_inicial

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)

st.set_page_config(page_title="Banco Ágil — Atendimento", page_icon="🏦")
st.title("🏦 Banco Ágil")
st.caption("Assistente virtual de atendimento")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.history = []
    st.session_state.encerrado = False
    # semeia o estado inicial no checkpointer
    st.session_state.graph.update_state(
        {"configurable": {"thread_id": st.session_state.thread_id}}, estado_inicial()
    )

cfg = {"configurable": {"thread_id": st.session_state.thread_id}}

for autor, texto in st.session_state.history:
    with st.chat_message(autor):
        st.markdown(texto)

if st.session_state.encerrado:
    st.info("Atendimento encerrado. Recarregue a página para iniciar um novo.")
else:
    entrada = st.chat_input("Digite sua mensagem...")
    if entrada:
        st.session_state.history.append(("user", entrada))
        with st.chat_message("user"):
            st.markdown(entrada)
        try:
            resultado = st.session_state.graph.invoke(
                {"messages": [HumanMessage(content=entrada)]}, cfg
            )
        except Exception as e:
            logging.exception("Erro na execução do grafo: %s", e)
            resposta = "Desculpe, tive uma instabilidade. Pode repetir, por favor?"
            resultado = None
        if resultado is not None:
            ultimas = [m for m in resultado["messages"] if isinstance(m, AIMessage) and m.content]
            resposta = ultimas[-1].content if ultimas else "..."
            st.session_state.encerrado = bool(resultado.get("encerrar"))
        st.session_state.history.append(("assistant", resposta))
        with st.chat_message("assistant"):
            st.markdown(resposta)
        if st.session_state.encerrado:
            st.rerun()
```

Nota: usa `graph.update_state` para semear o estado default no checkpointer da thread; a cada turno só injeta a nova `HumanMessage` (o reducer `add_messages` acumula, e o restante do estado persiste via `MemorySaver`).

- [ ] **Step 2: Garantir dados e chave**

Run: `python scripts/seed_data.py` e confirmar que `.env` existe com `GEMINI_API_KEY` (copiar de `.env.example`).
Expected: CSVs presentes; `.env` configurado.

- [ ] **Step 3: Verificação manual ponta-a-ponta**

Run: `streamlit run app.py`

Roteiro de teste manual (validar cada requisito do PDF):
1. **Auth falha 3x** → digitar CPF/data errados três vezes → encerra com mensagem gentil.
2. **Auth ok** (`123.456.789-01` / `1990-05-14`) → assistente pergunta como pode ajudar.
3. **Câmbio** → "qual a cotação do dólar?" → retorna valor; sem perceber transição.
4. **Consulta de limite** → "qual meu limite?" → R$ 2000,00.
5. **Aumento aprovado** → cliente Ana (score 620, teto 5000) pede R$ 4000 → aprovado; conferir linha em `data/solicitacoes_aumento_limite.csv` com `status_pedido=aprovado`.
6. **Aumento rejeitado → entrevista → reanálise** → pedir R$ 9000 → rejeitado → aceitar entrevista → responder renda/emprego/despesas/dependentes/dívidas → score atualiza em `clientes.csv` → Crédito reavalia.
7. **Encerrar a qualquer momento** → "quero encerrar" → finaliza.

Expected: todos os fluxos funcionam; transições imperceptíveis; erros (ex.: desligar internet no passo 3) não quebram a conversa.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: Streamlit chat UI wired to the agent graph"
```

---

### Task 16: README e verificação final

**Files:**
- Create: `README.md`

**Interfaces:**
- Produces: `README.md` com as 6 seções obrigatórias do PDF.

- [ ] **Step 1: Escrever `README.md`**

Estrutura obrigatória (preencher com o conteúdo real do projeto, reaproveitando `design.md`):

```markdown
# Agente Bancário Inteligente — Banco Ágil

## Visão Geral
[O que é: atendimento bancário multi-agente com um único assistente aparente.]

## Arquitetura do Sistema
[Diagrama de camadas + os 4 agentes, fluxos e manipulação de dados. Reaproveitar seções 3–4 do design.md. Explicar: gate determinístico de auth, router por intenção, handoffs via Command, escopo por subconjunto de tools, camada de repositório CSV.]

## Funcionalidades Implementadas
- Autenticação (CPF + data), 3 tentativas
- Consulta de limite
- Solicitação de aumento (log em CSV, aprovação por score)
- Entrevista de crédito com recálculo de score
- Câmbio via API externa
- Encerramento a qualquer momento
- Tratamento de erros gracioso

## Desafios Enfrentados e Soluções
- Handoff imperceptível → persona única + ausência de mensagens de transição
- Confiabilidade → regras críticas determinísticas (tools/funções puras), não no LLM
- Gate de auth imune a prompt injection → aresta de grafo, não instrução de prompt

## Escolhas Técnicas e Justificativas
- LangGraph (estado + handoffs explícitos), Gemini gemini-2.0-flash, AwesomeAPI (câmbio sem chave), Streamlit
- Camada de repositório única (testabilidade, tratamento de erro centralizado)

## Tutorial de Execução e Testes
1. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. `cp .env.example .env` e preencher `GEMINI_API_KEY`
4. `python scripts/seed_data.py`
5. `streamlit run app.py`
6. Testes: `pytest -v`

### Clientes de exemplo
| CPF | Data nasc. | Score | Uso |
|---|---|---|---|
| 123.456.789-01 | 1990-05-14 | 620 | aumento aprovado até R$5000 |
| 345.678.901-23 | 1998-03-27 | 280 | rejeição → entrevista |

## Limitações Conhecidas
- Escrita concorrente em CSV (race condition teórica) — migrar p/ SQLite como evolução.
- Estado de sessão in-memory (MemorySaver) — reinício zera conversas.
```

- [ ] **Step 2: Rodar suíte completa uma última vez**

Run: `pytest -v`
Expected: todos PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: complete README with architecture, setup and examples"
```

- [ ] **Step 4: Publicar no GitHub**

```bash
git branch -M main
# criar repositório público (via gh ou web) e:
git remote add origin <URL_DO_REPO_PUBLICO>
git push -u origin main
```

---

## Notas de execução

- **Ordem:** Tasks 1→16 respeitam dependências (dados → repositório → tools → runtime → nós → grafo → UI → docs).
- **TDD real** nas Tasks 3–9 (core determinístico). Nós de LLM (10–13) têm verificação de import + smoke test de integração (14) + validação manual (15) — porque comportamento conversacional não se testa bem com asserts.
- **Ambiente:** ativar venv e configurar `GEMINI_API_KEY` antes das Tasks 14–15 (que fazem/mockam chamadas ao LLM; a suíte usa mocks, mas a UI é real).
- **Se um teste de integração ficar frágil**, prefira testar o nó isolado (retorno `Command`) a orquestrar o grafo inteiro com fakes.
