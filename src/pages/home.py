"""Página inicial: resumo, retomada e próximas revisões."""

from __future__ import annotations

from datetime import date

import streamlit as st

from src.app_state import db
from src.navigation import ir
from src.services import question_service, revision_service, stats_service
from src.services.content_service import carregar_areas, nome_assunto


def render() -> None:
    st.title("Português por Lógica")
    st.markdown(
        "Não decore que uma palavra *é* adjetivo: **investigue** o que ela faz na frase. "
        "Cada resposta aqui é consequência de um raciocínio — classe, relação e contexto."
    )

    with db() as s:
        df = stats_service.tentativas_df(s)
        res = stats_service.resumo(df)
        pend = revision_service.pendentes(s)
        pend_info = [(r.assunto_id, r.proxima_data) for r in pend]
        proximas = [(r.assunto_id, r.proxima_data) for r in revision_service.todas(s) if r.proxima_data > date.today()][:5]
        ultimo = question_service.ultimo_assunto_estudado(s)
        seq = stats_service.sequencia(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Questões resolvidas", res.resolvidas)
    c2.metric("Taxa de acertos", f"{res.taxa:.0%}" if res.taxa is not None else "—")
    c3.metric("Revisões pendentes", len(pend_info))
    c4.metric("Sequência de dias", seq)
    if res.resolvidas == 0:
        st.caption("Ainda não há respostas registradas. As estatísticas aparecem conforme você pratica.")

    st.divider()
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader("Retomar estudos")
        if ultimo:
            st.markdown(f"Último assunto praticado: **{nome_assunto(ultimo)}**.")
            if st.button("Continuar este assunto", type="primary"):
                st.session_state["aprender_assunto"] = ultimo
                ir("aprender")
        else:
            st.markdown("Comece pela **Área dos Nomes**: o substantivo é o núcleo em torno do qual tudo se organiza.")
            if st.button("Começar pelo substantivo", type="primary"):
                st.session_state["aprender_assunto"] = "substantivo"
                ir("aprender")

        st.subheader("As áreas")
        for area in carregar_areas():
            with st.container(border=True):
                st.markdown(f"**{area.nome}** — {area.descricao}")
                st.caption(" · ".join(a.nome for a in area.assuntos))

    with col_b:
        st.subheader("Revisões")
        if pend_info:
            for assunto, quando in pend_info:
                st.markdown(f"- **{nome_assunto(assunto)}** (desde {quando:%d/%m})")
            if st.button("Revisar agora"):
                ir("revisoes")
        else:
            st.caption("Nenhuma revisão pendente hoje.")
        if proximas:
            st.markdown("**Próximas:**")
            for assunto, quando in proximas:
                st.markdown(f"- {nome_assunto(assunto)} — {quando:%d/%m}")

        st.subheader("Atalhos")
        if st.button("Analisar uma frase no Laboratório"):
            ir("laboratorio")
        if st.button("Colar uma questão de concurso"):
            ir("questoes")
