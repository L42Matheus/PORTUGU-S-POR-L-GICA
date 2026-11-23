"""Registro das páginas (para navegação e links entre páginas)."""

from __future__ import annotations

import streamlit as st

_PAGINAS: dict[str, st.Page] = {}


def paginas() -> dict[str, st.Page]:
    if not _PAGINAS:
        from src.pages import aprender, dashboard, exercicios, home, laboratorio, questoes, revisoes

        _PAGINAS.update(
            {
                "inicio": st.Page(home.render, title="Início", icon=":material/home:", url_path="inicio", default=True),
                "aprender": st.Page(aprender.render, title="Aprender", icon=":material/menu_book:", url_path="aprender"),
                "laboratorio": st.Page(laboratorio.render, title="Laboratório", icon=":material/science:", url_path="laboratorio"),
                "questoes": st.Page(questoes.render, title="Resolver Questões", icon=":material/quiz:", url_path="resolver"),
                "exercicios": st.Page(exercicios.render, title="Exercícios", icon=":material/edit_note:", url_path="exercicios"),
                "revisoes": st.Page(revisoes.render, title="Revisões", icon=":material/history:", url_path="revisoes"),
                "dashboard": st.Page(dashboard.render, title="Desempenho", icon=":material/insights:", url_path="desempenho"),
            }
        )
    return _PAGINAS


def ir(nome: str) -> None:
    st.switch_page(paginas()[nome])
