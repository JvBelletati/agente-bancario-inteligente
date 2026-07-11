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
