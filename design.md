# Design — Agente Bancário Inteligente (Banco Ágil)

> Documento de arquitetura e design da solução para o Desafio Técnico "Agente Bancário Inteligente".
> Serve como referência única do projeto e base para o plano de implementação.

## 1. Visão geral

Sistema de atendimento bancário multi-agente onde, para o cliente, existe **um único
assistente**, mas internamente há **4 agentes especializados** com handoffs implícitos,
orquestrados por um grafo de estados. Regras de negócio críticas (autenticação, checagem
de score, cálculo de score, escrita em CSV) são **determinísticas** (funções puras / tools),
enquanto o LLM cuida de conversa, extração de intenção e decisão de *quando* usar cada tool.

### Stack

| Camada | Tecnologia |
|---|---|
| Orquestração multi-agente | **LangGraph** (StateGraph + checkpointer) |
| LLM | **Gemini `gemini-2.0-flash`** via `langchain-google-genai` |
| API de câmbio | API dedicada sem chave (AwesomeAPI / exchangerate.host) |
| UI | **Streamlit** (chat único) |
| Dados | CSV via camada de repositório (`pandas`) |
| HTTP | `httpx` (timeout + status check) |
| Config | `python-dotenv` |
| Testes | `pytest` |

## 2. Princípio central

**Separar conversa (LLM) de regra de negócio (código determinístico).**
Autenticação, aprovação de limite, cálculo de score e I/O de CSV NÃO dependem do
julgamento do LLM — são tools/funções puras. Isso garante confiabilidade e é reforçado
por três mecanismos estruturais:

1. **Gate determinístico de autenticação** — antes de `autenticado == True`, o grafo força
   a Triagem. É uma aresta do grafo, não uma instrução de prompt (imune a prompt injection).
2. **Escopo por construção** — cada agente ReAct só enxerga um subconjunto de tools.
   O agente de Câmbio nem tem acesso à tool de crédito → "nenhum agente atua fora do escopo".
3. **Handoff implícito** — fluxo único de mensagens + persona/tom compartilhados, sem frases
   de transição. Para o cliente, é um assistente só.

## 3. Arquitetura

### 3.1 Camadas

```
UI Streamlit (chat único)
        │
Grafo LangGraph (estado compartilhado + roteamento)
   gate_auth ──não auth──► TRIAGEM
        │ auth
        ▼
     router ──► CRÉDITO ──handoff──► ENTREVISTA ──volta──► CRÉDITO
        └─────► CÂMBIO
   (tool "encerrar" disponível em qualquer nó → END)
        │
Tools / lógica determinística  →  camada de dados (CSV)
```

### 3.2 Estado compartilhado (`BankState`)

```python
class BankState(TypedDict):
    messages: Annotated[list, add_messages]

    # autenticação
    autenticado: bool
    tentativas_auth: int          # 0..3 → 3ª falha encerra
    cpf: str | None
    cliente: dict | None          # linha de clientes.csv em memória

    # roteamento
    active_agent: str             # "triagem" | "credito" | "entrevista" | "cambio"

    # contexto crédito/entrevista
    ultima_solicitacao: dict | None
    dados_entrevista: dict | None

    # controle de fluxo
    encerrar: bool
```

### 3.3 Nós e arestas

| Nó | Tipo | Tools | Saídas |
|---|---|---|---|
| `gate_auth` | função pura | — | `triagem` (não auth) · `router` (auth) |
| `triagem` | agente ReAct | `autenticar_cliente`, `encerrar` | `router` (ok) · `END` (3 falhas/encerrar) · self |
| `router` | LLM classificador leve | — | `credito` · `cambio` (por intenção) |
| `credito` | agente ReAct | `consultar_limite`, `registrar_solicitacao_aumento`, `avaliar_score_limite`, `iniciar_entrevista_credito`, `encerrar` | `entrevista` · `router` · `END` |
| `entrevista` | agente ReAct | `atualizar_score_cliente` (usa `calcular_score` internamente, não é tool exposta ao LLM), `retornar_para_credito`, `encerrar` | `credito` |
| `cambio` | agente ReAct | `consultar_cotacao`, `encerrar` | `router` · `END` |

### 3.4 Handoff (via `Command`)

```python
def iniciar_entrevista_credito(state) -> Command:
    return Command(goto="entrevista", update={"active_agent": "entrevista"})
```

Transição imperceptível garantida por: (a) sem mensagem de transição; (b) persona única nos
prompts; (c) `active_agent` sticky — o especialista ativo responde os próximos turnos até
dar handoff ou devolver o controle (a Entrevista não é interrompida pelo router no meio).

### 3.5 Roteamento determinístico

- **Auth:** `tentativas_auth` incrementado por código na tool `autenticar_cliente`.
  `>= 3 e falhou` → `END` com mensagem gentil.
- **Gate:** `gate_auth` é função Python (`if not autenticado: goto triagem`).
- **Encerramento:** tool `encerrar` seta `encerrar=True`; checkpoint condicional em cada nó → `END`.

### 3.6 Persistência de sessão

`MemorySaver` (checkpointer in-memory), `thread_id` = id da sessão Streamlit. Estado isolado
por usuário/aba. Upgrade opcional documentado: `SqliteSaver` para persistência entre reinícios.

## 4. Modelo de dados

### 4.1 `clientes.csv` (auth + store de score/limite)

| coluna | tipo | notas |
|---|---|---|
| `cpf` | string (11 dígitos, só números) | chave de auth; tool normaliza entrada |
| `nome` | string | saudação personalizada |
| `data_nascimento` | date ISO `YYYY-MM-DD` | 2º fator de auth |
| `limite_atual` | float | consulta + base do aumento |
| `score` | int (0–1000) | atualizado pela Entrevista |

Auth = match exato de `cpf` **e** `data_nascimento`. Semear ~8–10 clientes cobrindo faixas
de score variadas (inclui caso de score baixo p/ demonstrar rejeição→entrevista e caso alto).

### 4.2 `score_limite.csv` (faixa de score → limite máximo)

| score_min | score_max | limite_maximo |
|---|---|---|
| 0 | 299 | 500 |
| 300 | 499 | 2.000 |
| 500 | 699 | 5.000 |
| 700 | 849 | 15.000 |
| 850 | 1000 | 50.000 |

### 4.3 `solicitacoes_aumento_limite.csv` (log de saída — colunas exatas do PDF)

| coluna | tipo |
|---|---|
| `cpf_cliente` | string |
| `data_hora_solicitacao` | timestamp ISO 8601 |
| `limite_atual` | float |
| `novo_limite_solicitado` | float |
| `status_pedido` | `pendente` → `aprovado`/`rejeitado` |

**Fluxo 2 fases:** `registrar_solicitacao_aumento` anexa linha `pendente`; `avaliar_score_limite`
compara `novo_limite <= limite_maximo(score)` e atualiza a mesma linha para `aprovado`/`rejeitado`.

### 4.4 Fórmula de score (função pura, clamp [0,1000])

```python
def calcular_score(renda, tipo_emprego, despesas, num_dependentes, tem_dividas) -> int:
    score = (
        (renda / (despesas + 1)) * PESO_RENDA            # 30
        + PESO_EMPREGO[tipo_emprego]                     # formal 300 / autônomo 200 / desempregado 0
        + PESO_DEPENDENTES[bucket_dep(num_dependentes)]  # 0→100,1→80,2→60,"3+"→30
        + PESO_DIVIDAS[tem_dividas]                      # sim -100 / não +100
    )
    return max(0, min(1000, round(score)))
```

Encapsula: normalização de `tipo_emprego`/`tem_dividas` (case-insensitive, acentos), bucket
`num_dependentes >= 3` → `"3+"`, guarda de divisão (`despesas + 1`), validação de entradas
(negativos/não-numéricos → erro tratável, agente re-pergunta).

### 4.5 Camada de dados (`repository.py`)

ÚNICA porta de I/O de CSV. Funções: `buscar_cliente`, `atualizar_score`, `append_solicitacao`,
`atualizar_status_solicitacao`, `carregar_tabela_score`. Centraliza tratamento de erro e torna
as tools testáveis com repositório mockado.

> Limitação conhecida: read-modify-write em CSV tem race condition teórica. Aceitável no escopo
> (demo single-user por sessão); documentado no README com "migrar p/ SQLite" como evolução.

## 5. Tratamento de erros

| Erro esperado | Onde | Comportamento |
|---|---|---|
| CSV ausente/corrompido | `repository.py` | mensagem de instabilidade + log técnico |
| API câmbio fora/timeout | tool `consultar_cotacao` | "não consegui a cotação agora" |
| Entrada inválida | validação na tool | agente re-pergunta, não derruba fluxo |
| Ação fora de escopo | garantido por construção | tool inexistente no nó |
| Exceção inesperada | wrapper do nó | mensagem gentil + `logging.exception` |

Módulo `logging` central (arquivo `logs/app.log` + console) para análise técnica posterior.

## 6. Estrutura de pastas

```
agente_bancario/
├── app.py                      # UI Streamlit
├── src/
│   ├── config.py               # modelo LLM, pesos, paths, env
│   ├── graph/
│   │   ├── state.py            # BankState
│   │   ├── builder.py          # build_graph()
│   │   ├── router.py           # gate_auth + router por intenção
│   │   └── nodes/{triagem,credito,entrevista,cambio}.py
│   ├── tools/{auth,credito,score,cambio,common}.py
│   ├── data/repository.py      # única porta de I/O de CSV
│   └── prompts/                # system prompts por agente
├── data/{clientes,score_limite,solicitacoes_aumento_limite}.csv
├── scripts/seed_data.py
├── tests/
├── logs/
├── .env.example                # GEMINI_API_KEY=...
├── requirements.txt
└── README.md
```

## 7. Testes (pytest)

- `test_score.py` — faixas, buckets, dívidas, clamp, entradas inválidas.
- `test_credito.py` — aprovação nas bordas de faixa.
- `test_auth.py` — CPF com/sem formatação, data errada, inexistente, contagem de tentativas.
- `test_repository.py` — leitura, update de score (round-trip), append, arquivo ausente.
- `test_graph.py` (opcional) — smoke test do gate de auth + um handoff com LLM stub.

## 8. README (seções obrigatórias do PDF)

Visão Geral · Arquitetura (diagrama + 4 agentes/fluxos/dados) · Funcionalidades · Desafios e
soluções · Escolhas técnicas e justificativas · Tutorial de execução e testes.

## 9. Requisitos do PDF → onde são atendidos (rastreabilidade)

| Requisito | Atendido em |
|---|---|
| Triagem autentica (CPF+nasc.) contra `clientes.csv` | nó `triagem` + tool `autenticar_cliente` + `repository` |
| Até 3 tentativas, encerra na 3ª falha | `tentativas_auth` + aresta condicional → END |
| Redireciona só após auth | `gate_auth` determinístico |
| Consulta de limite | tool `consultar_limite` |
| Solicitação de aumento → `solicitacoes_aumento_limite.csv` | tool `registrar_solicitacao_aumento` (2 fases) |
| Checagem via `score_limite.csv` → aprovado/rejeitado | tool `avaliar_score_limite` |
| Rejeitado → oferece Entrevista | lógica no nó `credito` + `iniciar_entrevista_credito` |
| Entrevista coleta 5 dados → recalcula score | nó `entrevista` + `calcular_score` |
| Atualiza score em `clientes.csv` → volta ao Crédito | `atualizar_score_cliente` + `retornar_para_credito` |
| Câmbio via API externa | tool `consultar_cotacao` |
| Encerramento a qualquer momento | tool `encerrar` + checkpoint em cada nó |
| Handoff implícito / persona única | prompts compartilhados + sem msg de transição |
| Escopo restrito por agente | subset de tools por nó |
| Tratamento de erros gracioso | camada de erros (seção 5) |
| UI Streamlit | `app.py` |
| README + estrutura modular | seção 8 + seção 6 |

## 10. Decisões em aberto (para o plano de implementação)

- Modelo Gemini exato (`gemini-2.0-flash` vs `2.5-flash`) — confirmar no `config.py`.
- Endpoint de câmbio primário (AwesomeAPI BR vs exchangerate.host) e moedas suportadas.
- Quantidade/perfil exato dos clientes sintéticos em `seed_data.py`.
- `test_graph.py`: incluir agora ou deixar como stretch.
