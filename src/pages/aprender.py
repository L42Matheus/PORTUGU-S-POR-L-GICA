"""Modo Aprender: conceito, regras, exemplos, comparação e Gramática em Código."""

from __future__ import annotations

import streamlit as st

from src.app_state import db
from src.components import question_card
from src.components.theme import legenda
from src.services import question_service
from src.services.content_service import carregar_areas, licao_do_assunto, mapa_assuntos


def _exemplos(titulo: str, lista, tipo: str) -> None:
    st.markdown(f"**{titulo}**")
    for e in lista:
        frase = e.frase.replace(e.destaque, f"**{e.destaque}**", 1) if e.destaque else e.frase
        icone = "✔" if tipo == "ex" else "✘"
        st.markdown(f"{icone} *{frase}* — {e.explicacao}")


def render() -> None:
    st.title("Aprender")
    areas = carregar_areas()
    pre = st.session_state.pop("aprender_assunto", None)
    if pre and pre in mapa_assuntos():
        st.session_state["apr_area"] = mapa_assuntos()[pre][0].id
        st.session_state["apr_assunto"] = pre

    st.session_state.setdefault("apr_area", areas[0].id)
    area_id = st.segmented_control(
        "Área", [a.id for a in areas], format_func=lambda i: next(a.nome for a in areas if a.id == i), key="apr_area"
    ) or areas[0].id
    area = next(a for a in areas if a.id == area_id)
    st.caption(area.conceito_central)

    ids = [s.id for s in area.assuntos]
    if st.session_state.get("apr_assunto") not in ids:
        st.session_state["apr_assunto"] = ids[0]
    assunto = st.radio("Assunto", ids, format_func=lambda i: mapa_assuntos()[i][1], horizontal=True, key="apr_assunto")
    lic = licao_do_assunto(assunto)
    if lic is None:
        st.warning("Conteúdo ainda não cadastrado para este assunto.")
        return

    st.header(lic.titulo)
    st.caption(lic.classe_ou_expressao)
    t1, t2, t3, t4, t5, t6 = st.tabs(["Conceito", "Regras e exceções", "Exemplos", "Comparar contextos", "Gramática em Código", "Exercícios"])

    with t1:
        st.markdown(lic.conceito)
        for sub in lic.subtopicos:
            with st.expander(sub.titulo):
                st.markdown(sub.texto)
                for ex in sub.exemplos:
                    st.markdown(f"- *{ex}*")
    with t2:
        st.markdown("**Regras de investigação**")
        for r in lic.regras:
            st.markdown(f"- {r}")
        st.markdown("**Exceções e casos relevantes**")
        for e in lic.excecoes:
            st.markdown(f"- {e}")
    with t3:
        _exemplos("Exemplos", lic.exemplos, "ex")
        st.divider()
        _exemplos("Contraexemplos (armadilhas comuns)", lic.contraexemplos, "contra")
    with t4:
        st.markdown("A mesma forma pode mudar de classe conforme a relação com as outras palavras:")
        st.table(
            [{"Frase": c.frase, "Palavra": c.palavra, "Classificação": c.classificacao, "Por quê": c.explicacao} for c in lic.comparacoes]
        )
    with t5:
        st.info(
            "O código abaixo é um **modelo didático de raciocínio**, não um algoritmo capaz de resolver sozinho a gramática. "
            "Funções como `caracteriza_nome()` exigem compreender o sentido — é justamente isso que você treina."
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Fluxograma**")
            st.graphviz_chart(lic.logica.fluxograma, use_container_width=True)
        with c2:
            st.markdown("**Pseudocódigo**")
            st.code(lic.logica.pseudocodigo, language="text")
            st.markdown("**Python**")
            st.code(lic.logica.python, language="python")
        st.markdown("**Limitações e exceções do modelo**")
        for lim in lic.logica.limitacoes:
            st.markdown(f"- {lim}")
        st.caption("Analogias em Java estão planejadas para uma versão futura.")
    with t6:
        chave = f"apr_{assunto}"
        if question_card.questao_atual(chave) is None or st.button("Outra questão deste assunto"):
            with db() as s:
                q = question_service.sortear(question_service.filtrar(assunto=assunto), s)
            question_card.definir_questao(chave, q.id if q else None)
        if question_card.questao_atual(chave) is None:
            st.caption("Ainda não há questões cadastradas para este assunto.")
        else:
            question_card.render(chave, modo="aprender")

    with st.expander("Legenda de cores das classes"):
        st.markdown(legenda(), unsafe_allow_html=True)
