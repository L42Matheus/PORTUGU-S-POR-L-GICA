"""Português por Lógica — ponto de entrada da aplicação Streamlit.

Execute com:  streamlit run app.py
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from src.app_state import ia  # noqa: E402
from src.components.theme import aplicar_preferencias, painel_acessibilidade  # noqa: E402
from src.navigation import paginas  # noqa: E402

st.set_page_config(page_title="Português por Lógica", page_icon=":material/psychology:", layout="wide")

p = paginas()
nav = st.navigation(
    {
        "Estudo": [p["inicio"], p["aprender"], p["laboratorio"], p["questoes"]],
        "Prática": [p["exercicios"], p["revisoes"], p["dashboard"]],
    }
)

with st.sidebar:
    st.markdown("### Português por Lógica")
    st.caption("Gramática como raciocínio estruturado.")
painel_acessibilidade()
st.sidebar.caption(
    f"IA: {'ativa (' + ia().provedor.nome + ')' if ia().disponivel else 'não configurada — modo offline com conteúdo revisado'}"
)
aplicar_preferencias()

nav.run()
