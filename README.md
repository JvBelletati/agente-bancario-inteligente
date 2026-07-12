# Agente Bancário Inteligente — Banco Ágil

[![CI/CD](https://github.com/JvBelletati/agente-bancario-inteligente/actions/workflows/ci.yml/badge.svg)](https://github.com/JvBelletati/agente-bancario-inteligente/actions/workflows/ci.yml)
[![Drift Check](https://github.com/JvBelletati/agente-bancario-inteligente/actions/workflows/drift-check.yml/badge.svg)](https://github.com/JvBelletati/agente-bancario-inteligente/actions/workflows/drift-check.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/status-portfolio-orange?style=flat-square)

Assistente virtual de atendimento bancário construído com **LangGraph** + **Claude** (ou Gemini), que para
o cliente aparenta ser um único atendente, mas internamente orquestra **4 agentes
especializados** (Triagem, Crédito, Entrevista de Crédito e Câmbio) com handoffs implícitos.

## Visão Geral

O Banco Ágil é um chatbot de atendimento bancário desenvolvido para o desafio técnico "Agente
Bancário Inteligente". O cliente interage com um único chat (Streamlit); por trás dele, um grafo
de estados do LangGraph decide qual "especialista" deve responder a cada turno e troca de
especialista sem que isso seja percebido pelo usuário (sem mensagens de transição, com uma
persona e tom únicos em todos os prompts).

Regras de negócio críticas — autenticação, cálculo de score de crédito, aprovação/rejeição de
aumento de limite e leitura/escrita dos dados em CSV — são **determinísticas**: implementadas
como funções Python puras e *tools*, não deixadas a cargo do julgamento do LLM. O papel do LLM é
conduzir a conversa, extrair intenção e decidir *quando* chamar cada tool. Essa separação (LLM só
para linguagem, código determinístico para regra) é o princípio central do projeto e é o que
permite confiar no comportamento do agente em pontos sensíveis como autenticação e aprovação de
crédito.

## Arquitetura do Sistema

### Camadas

```
UI Streamlit (chat único)
        │
Grafo LangGraph (estado compartilhado + roteamento)
   gate_auth
     ├─ não autenticado ──────────────────────────────► TRIAGEM
     ├─ autenticado + especialista ativo (sticky) ────► CRÉDITO / ENTREVISTA / CÂMBIO (direto)
     └─ autenticado + nenhum especialista ativo ──────► router ──► CRÉDITO ──handoff──► ENTREVISTA
                                                               └──► CÂMBIO      (retorna a CRÉDITO)
   (CRÉDITO e CÂMBIO voltam ao router via a tool "outro_assunto"; "encerrar" → END em
    qualquer nó conversacional; gate_auth reavalia esses ramos a cada turno de mensagem)
        │
Tools / lógica determinística  →  camada de dados (CSV)
```

### Os 4 agentes

| Nó | Tipo | Tools que enxerga | Saídas possíveis |
|---|---|---|---|
| `gate_auth` | função pura (não-LLM) | — | `END` (se `encerrar`) · `triagem` (não autenticado) · `credito`/`entrevista`/`cambio` direto — bypass do router — quando autenticado e há um especialista "sticky" ativo (`active_agent`) · `router` quando autenticado e nenhum especialista está ativo |
| `triagem` | agente ReAct | `autenticar_cliente`, `encerrar` | `END` (autenticou; `router` entra no turno seguinte via `gate_auth`) · `END` (3ª falha ou encerramento) · permanece em si mesmo |
| `router` | classificador leve por LLM | — | `credito` · `cambio`, conforme a intenção do cliente |
| `credito` | agente ReAct | `_consultar_limite`, `_registrar_solicitacao_aumento`, `_avaliar_score_limite`, `iniciar_entrevista_credito`, `outro_assunto`, `encerrar` | `entrevista` (via `iniciar_entrevista_credito`) · `router` (via `outro_assunto`) · `END` |
| `entrevista` | agente ReAct | `_atualizar_score_cliente`, `retornar_para_credito` | `credito` (via `retornar_para_credito`, sempre volta) |
| `cambio` | agente ReAct | `consultar_cotacao`, `outro_assunto`, `encerrar` | `router` (via `outro_assunto`) · `END` |

As tools com nome iniciado por `_` (`_consultar_limite`, `_registrar_solicitacao_aumento`,
`_avaliar_score_limite`, `_atualizar_score_cliente`) são *closures* definidas dentro do nó,
fechadas sobre o `cpf` já autenticado no estado — assim o LLM nunca informa de qual cliente
quer os dados, apenas decide *que* ação tomar, e não há como consultar/alterar dados de
outro CPF. `calcular_score` (`src/tools/score.py`) é uma função auxiliar interna chamada por
`atualizar_score_cliente` — não é exposta como tool ao LLM.

Cada agente ReAct só tem acesso ao subconjunto de tools listado acima — por exemplo, o agente de
Câmbio nem sequer possui a tool de crédito na sua lista de *tools*, então "nenhum agente atua
fora do escopo" é garantido **por construção**, não por instrução de prompt.

### Mecanismos estruturais de confiabilidade

1. **Gate determinístico de roteamento (`gate_auth`)** — toda mensagem passa antes por uma
   aresta de grafo em Python puro (sem LLM), que decide o próximo nó nesta ordem: (1) se
   `encerrar` estiver setado no estado, vai direto para `END`; (2) se o cliente ainda não está
   autenticado, força a passagem pela Triagem; (3) se já está autenticado e existe um
   especialista "sticky" ativo (`active_agent` igual a `credito`, `entrevista` ou `cambio`), vai
   **direto** para esse nó — sem passar pelo `router`; (4) só quando autenticado e sem nenhum
   especialista ativo é que o `router` (classificador por LLM) entra em ação. Ou seja, o
   `router_node` roda apenas quando não há especialista em curso, não em todo turno autenticado.
   Como é código Python com `if`s, não uma instrução de prompt, esse roteamento é imune a
   tentativas de prompt injection que peçam para "pular a autenticação" ou "trocar de
   especialista".
2. **Escopo restrito por construção** — como descrito acima, cada nó ReAct é instanciado com sua
   própria lista de tools; o LLM literalmente não tem como chamar uma tool que não lhe foi
   passada. As tools de crédito/entrevista, além disso, são fechadas (*closures*) sobre o `cpf`
   já autenticado no estado, então nem o LLM decide de qual cliente são os dados.
3. **Handoff implícito via `Command`** — a troca de especialista é feita retornando um
   `Command(goto="entrevista", update={"active_agent": "entrevista"})` a partir de uma tool de
   controle (ex.: `iniciar_entrevista_credito`, `retornar_para_credito`, `outro_assunto`). Não há
   mensagem de transição, e `active_agent` é "sticky": o especialista ativo continua respondendo
   os próximos turnos (via o bypass do `gate_auth` descrito no item 1) até ele mesmo devolver o
   controle ou fazer handoff — a Entrevista, por exemplo, não é interrompida pelo router no meio
   da coleta de dados.

### Estado compartilhado (`BankState`)

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

### Modelo de dados

**`data/clientes.csv`** — autenticação + score/limite atuais:

| coluna | tipo | notas |
|---|---|---|
| `cpf` | string, 11 dígitos | chave de autenticação (tool normaliza pontuação na entrada) |
| `nome` | string | usado na saudação personalizada |
| `data_nascimento` | data ISO `YYYY-MM-DD` | 2º fator de autenticação |
| `limite_atual` | float | usado na consulta de limite e como base do pedido de aumento |
| `score` | int (0–1000) | recalculado e atualizado pela Entrevista de crédito |

**`data/score_limite.csv`** — faixa de score → limite máximo aprovável:

| score_min | score_max | limite_maximo |
|---|---|---|
| 0 | 299 | 500 |
| 300 | 499 | 2.000 |
| 500 | 699 | 5.000 |
| 700 | 849 | 15.000 |
| 850 | 1000 | 50.000 |

**`data/solicitacoes_aumento_limite.csv`** — log de pedidos de aumento (criado dinamicamente na
primeira solicitação, não versionado no repositório):

| coluna | tipo |
|---|---|
| `cpf_cliente` | string |
| `data_hora_solicitacao` | timestamp ISO 8601 |
| `limite_atual` | float |
| `novo_limite_solicitado` | float |
| `status_pedido` | `pendente` → `aprovado` / `rejeitado` |

O fluxo de aumento de limite é em duas fases: `registrar_solicitacao_aumento` grava a linha como
`pendente`; em seguida `avaliar_score_limite` compara o `novo_limite` com o `limite_maximo` da
faixa de score do cliente e atualiza a **mesma linha** para `aprovado` ou `rejeitado`.

Toda leitura/escrita de CSV passa por uma única camada de repositório
(`src/data/repository.py`): `obter_cliente_por_cpf`, `buscar_cliente`, `atualizar_score`,
`append_solicitacao`, `atualizar_status_solicitacao`, `carregar_tabela_score`. Isso centraliza o
tratamento de erro (arquivo ausente/corrompido) e torna as *tools* testáveis com CSVs de teste
isolados, sem tocar nos dados reais.

### Tratamento de erros

| Erro esperado | Onde é tratado | Comportamento |
|---|---|---|
| CSV ausente/corrompido | `repository.py` | mensagem de instabilidade ao usuário + log técnico (`logging.exception`) |
| API de câmbio fora do ar / timeout | tool `consultar_cotacao` | resposta amigável ("não consegui a cotação agora"), sem quebrar a conversa |
| Entrada inválida (ex.: dependentes negativos, tipo de emprego não reconhecido) | validação na tool | o agente re-pergunta ao cliente, sem derrubar o fluxo |
| Ação fora de escopo | garantido por construção | a tool correspondente simplesmente não existe naquele nó |
| Exceção inesperada em qualquer nó | wrapper de execução em `app.py` / runtime dos nós | mensagem gentil ao usuário + `logging.exception` para investigação posterior |

Log central em `logs/app.log` (arquivo) + console, configurado em `app.py` via módulo
`logging` padrão do Python.

## Funcionalidades Implementadas

- **Autenticação** por CPF + data de nascimento contra `clientes.csv`, com até 3 tentativas —
  a 3ª falha encerra o atendimento com uma mensagem educada.
- **Consulta de limite de crédito** atual do cliente autenticado.
- **Solicitação de aumento de limite**, registrada em `solicitacoes_aumento_limite.csv` e
  avaliada automaticamente contra a tabela `score_limite.csv` (aprovação/rejeição por faixa de
  score).
- **Entrevista de crédito**: quando o pedido de aumento é rejeitado, o agente de Crédito oferece
  a Entrevista, que coleta 5 dados financeiros (renda, tipo de emprego, despesas, número de
  dependentes, existência de dívidas), recalcula o score do cliente e atualiza
  `clientes.csv`, retornando o controle ao agente de Crédito para retomar o pedido.
- **Câmbio**: cotação de moedas via API externa pública (AwesomeAPI), sem necessidade de chave.
- **Encerramento do atendimento a qualquer momento**, disponível em todos os nós conversacionais.
- **Tratamento de erros gracioso** em toda a aplicação (ver tabela na seção de Arquitetura).
- **UI de chat única** em Streamlit, com histórico de conversa e sessão isolada por aba/usuário
  (via `thread_id`).

## Desafios Enfrentados e Soluções

- **Handoff precisa ser imperceptível para o usuário, mas os agentes são internamente
  separados.** Solução: persona e tom compartilhados em todos os prompts de sistema
  (`src/prompts/personas.py`), nenhuma mensagem de transição ao trocar de nó, e `active_agent`
  sticky no estado — o especialista atual segue respondendo até fazer handoff explícito.
- **Confiabilidade em pontos sensíveis (autenticação, aprovação de crédito, cálculo de score).**
  Um LLM pode ser inconsistente ou manipulado; a solução foi tirar essas decisões do LLM e
  implementá-las como funções puras/tools determinísticas, testadas com `pytest` (faixas de
  score, bordas de aprovação, formatação de CPF, clamps, etc.), enquanto o LLM só decide *quando*
  chamá-las.
- **Gate de autenticação precisa ser imune a prompt injection** (ex.: um usuário tentando
  convencer o LLM de que "já está autenticado" ou pedindo para "ignorar as instruções
  anteriores"). Solução: o gate (`gate_auth`) é uma aresta condicional do grafo — código Python
  puro que olha o campo `autenticado` do estado — e não uma instrução dentro do prompt do LLM.
  Não existe caminho no grafo que leve a um nó pós-autenticação sem passar por essa checagem.
- **`ToolMessage` vazio derrubando o runtime ReAct.** Tools de controle (como as de handoff e
  encerramento) não retornam texto para o usuário; para não gerar `ToolMessage` vazio quebrando o
  histórico da conversa, o runtime dos agentes garante sempre um conteúdo mínimo nessas
  respostas.
- **Testar comportamento conversacional (nós de LLM) sem tornar os testes frágeis.** A suíte usa
  TDD real e determinístico para o núcleo (score, crédito, autenticação, repositório — Tasks
  3–9), e para os nós que envolvem LLM prioriza testar o nó isolado (verificando o `Command`
  retornado) em vez de orquestrar o grafo inteiro com múltiplos fakes encadeados, o que tende a
  quebrar por motivos não relacionados ao que está sendo testado.

## Escolhas Técnicas e Justificativas

| Escolha | Justificativa |
|---|---|
| **LangGraph** (`StateGraph` + `MemorySaver`) | Estado compartilhado explícito e handoffs entre agentes como transições de grafo (`Command`), em vez de um único prompt gigante tentando simular múltiplos papéis — mais previsível e testável. |
| **LLM multi-provedor** — Claude (`langchain-anthropic`, padrão) ou Gemini (`langchain-google-genai`) | A camada de LLM é agnóstica de provedor (abstração de `ChatModel` do LangChain), então troca-se o provedor/modelo só por env (`LLM_PROVIDER`, `ANTHROPIC_MODEL`, `GEMINI_MODEL`) sem tocar em `run_react_turn`, router ou nós. Claude por padrão pelo tool-calling confiável; um modelo mais leve (`claude-sonnet-5`/`claude-haiku-4-5`) costuma ser melhor custo/latência num chatbot multi-agente. |
| **AwesomeAPI** para câmbio | API pública sem necessidade de chave/cadastro, reduzindo fricção de setup para quem for rodar o projeto. |
| **Streamlit** para a UI | Chat funcional com pouquíssimo código, permitindo focar o esforço na lógica multi-agente em vez de front-end. |
| **CSV + camada única de repositório (`pandas`/`csv`)** | Atende ao requisito do desafio (dados em CSV) mantendo toda a I/O centralizada em `src/data/repository.py` — isso torna as *tools* testáveis com arquivos de teste isolados e centraliza o tratamento de erros (arquivo ausente/corrompido) em um único lugar. |
| **Funções puras para regras de negócio** (score, aprovação de limite) | Determinismo e testabilidade via `pytest`, sem depender do "humor" do LLM em decisões sensíveis. |
| **`MemorySaver` (checkpointer in-memory)** | Simples e suficiente para uma demo/sessão; troca deliberada de durabilidade por simplicidade (ver Limitações Conhecidas). |

## Tutorial de Execução e Testes

1. Criar e ativar o ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Linux/Mac
   .venv\Scripts\activate           # Windows
   ```
2. Instalar as dependências:
   ```bash
   pip install -r requirements.txt
   ```
   > Em alguns ambientes Windows sem permissão de escrita no Python global, pode ser necessário
   > `pip install --user -r requirements.txt`.
3. Configurar variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```
   e preencher a chave do provedor no `.env`:
   - **Claude (padrão):** `ANTHROPIC_API_KEY`. Opcional: `ANTHROPIC_MODEL` (ex.: `claude-sonnet-5` ou `claude-haiku-4-5` para menor custo/latência).
   - **Gemini:** defina `LLM_PROVIDER=google` e `GEMINI_API_KEY`.
4. Gerar os dados de exemplo (clientes e tabela de score→limite):
   ```bash
   python scripts/seed_data.py
   ```
5. Rodar a aplicação:
   ```bash
   streamlit run app.py
   ```
6. Rodar a suíte de testes:
   ```bash
   python -m pytest -v
   ```
   Resultado esperado: 32 testes, todos `PASSED`.

### Clientes de exemplo

A base gerada por `scripts/seed_data.py` (`data/clientes.csv`) contém 10 clientes sintéticos
cobrindo diferentes faixas de score. Dois exemplos úteis para testar os principais fluxos:

| CPF | Data nasc. | Score | Uso |
|---|---|---|---|
| 123.456.789-01 | 1990-05-14 | 620 | Score na faixa 500–699 (limite máximo R$ 5.000) → pedido de aumento até R$ 5.000 é **aprovado** |
| 345.678.901-23 | 1998-03-27 | 280 | Score na faixa 0–299 (limite máximo R$ 500) → qualquer aumento acima disso é **rejeitado**, e o agente de Crédito oferece a Entrevista para recalcular o score |

(CPF pode ser digitado com ou sem formatação — a tool de autenticação normaliza a entrada
removendo pontuação antes de comparar com a base.)

## Limitações Conhecidas

- **Estado de sessão in-memory (`MemorySaver`)**: o checkpointer do LangGraph guarda o histórico
  de conversa apenas em memória do processo. Reiniciar a aplicação (ou o processo do Streamlit)
  zera todas as conversas em andamento. Evolução possível: trocar por `SqliteSaver` (ou outro
  checkpointer persistente) para manter sessões entre reinícios.
- **Escrita concorrente em CSV**: o padrão *read-modify-write* usado em `repository.py` (ex.:
  `atualizar_score`, `atualizar_status_solicitacao`) tem uma condição de corrida teórica se dois
  processos escreverem no mesmo CSV ao mesmo tempo. Aceitável no escopo deste desafio (demo
  single-user por sessão), mas não deve ser usado como está em um cenário multiusuário
  concorrente real. Evolução possível: migrar a camada de dados para SQLite (ou outro banco com
  transações), mantendo a mesma interface de `repository.py`.
