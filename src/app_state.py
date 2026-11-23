"""Recursos compartilhados da aplicação Streamlit (banco e IA)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st
from sqlalchemy.orm import Session

from src.core.database import inicializar, sessao
from src.services.ai_service import ServicoIA


@st.cache_resource(show_spinner=False)
def _banco():
    return inicializar()


@contextmanager
def db() -> Iterator[Session]:
    _, fabrica = _banco()
    with sessao(fabrica) as s:
        yield s


@st.cache_resource(show_spinner=False)
def ia() -> ServicoIA:
    return ServicoIA()


def aviso_ia_indisponivel() -> None:
    st.info(
        "**Análise livre por IA indisponível.** Nenhuma chave de API foi configurada "
        "(veja `.env.example`). Conteúdos, exercícios e frases pré-validadas continuam funcionando; "
        "nenhuma análise fictícia será exibida."
    )
