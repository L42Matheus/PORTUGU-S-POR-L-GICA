"""Exercícios: modos de estudo e simulados."""

from __future__ import annotations

import streamlit as st

from src.app_state import db
from src.components import question_card
from src.services import question_service
from src.services.content_service import carregar_areas

MODOS = {
    "treino": ("Treino por área", "Questões de todos os tipos, filtradas por área e nível."),
    "identificar": ("Identificar", "Uma palavra é destacada: classifique-a."),
    "relacionar": ("Relacionar", "Ligue palavras a núcleos, modificadores ou conectivos."),
    "comparar": ("Comparar", "A mesma palavra em frases diferentes pode ter classes diferentes."),
    "encontrar_erro": ("Encontrar o erro", "Uma análise propositalmente incorreta: ache e corrija o problema."),
    "justificar": ("Justificar", "Explique seu raciocínio com texto livre."),
    "simulado": ("Simulado", "Bateria de questões com resultado final registrado."),
}
DIFS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}


def _filtros(prefixo: str) -> tuple[str | None, str | None]:
    areas = carregar_areas()
    c1, c2 = st.columns(2)
    area = c1.selectbox("Área", [None] + [a.id for a in areas], format_func=lambda i: "Todas" if i is None else next(a.nome for a in areas if a.id == i), key=f"{prefixo}_area")
    dif = c2.selectbox("Nível", [None, *DIFS], format_func=lambda d: "Todos" if d is None else DIFS[d], key=f"{prefixo}_dif")
    return area, dif


def _treino(modo: str) -> None:
    area, dif = _filtros("ex")
    tipos = question_service.MODOS_TIPOS.get(modo)
    cands = question_service.filtrar(area=area, dificuldade=dif, tipos=tipos)
    st.caption(f"{len(cands)} questão(ões) disponível(is) com esses filtros.")
    chave = f"ex_{modo}"
    atual = question_card.questao_atual(chave)
    if atual is None or st.button("Nova questão", type="primary"):
        with db() as s:
            q = question_service.sortear([c for c in cands if not atual or c.id != atual.id] or cands, s)
        question_card.definir_questao(chave, q.id if q else None)
        if atual is not None:
            st.rerun()
    if question_card.questao_atual(chave) is None:
        st.info("Nenhuma questão encontrada com esses filtros.")
        return
    question_card.render(chave, modo=modo)


def _simulado() -> None:
    sim = st.session_state.get("sim")
    if sim is None:
        area, dif = _filtros("sim")
        disp = [q for q in question_service.filtrar(area=area, dificuldade=dif) if q.tipo != "justificativa"]
        if not disp:
            st.info("Não há questões para esses filtros.")
            return
        n = st.slider("Número de questões", 1, min(30, len(disp)), min(10, len(disp)))
        if st.button("Iniciar simulado", type="primary"):
            qs = question_service.montar_simulado(n, area, dif)
            with db() as s:
                registro = question_service.iniciar_simulado(s, len(qs), area, dif)
                sid = registro.id
            st.session_state["sim"] = {"id": sid, "qids": [q.id for q in qs], "i": 0, "fim": False}
            question_card.definir_questao("sim_q", qs[0].id)
            st.rerun()
        return

    if sim["fim"]:
        st.success(f"Simulado concluído: **{sim['acertos']} de {sim['total']}** ({sim['acertos'] / sim['total']:.0%}).")
        st.caption("O resultado foi registrado no histórico de simulados (página Desempenho).")
        if st.button("Novo simulado"):
            st.session_state.pop("sim")
            st.rerun()
        return

    i, total = sim["i"], len(sim["qids"])
    st.progress(i / total, text=f"Questão {i + 1} de {total}")
    res = question_card.render("sim_q", modo="simulado", simulado_id=sim["id"], permitir_semelhante=False)
    if res is not None:
        ultimo = i + 1 >= total
        if st.button("Concluir simulado" if ultimo else "Próxima questão", type="primary"):
            if ultimo:
                with db() as s:
                    r = question_service.concluir_simulado(s, sim["id"])
                    sim.update(fim=True, acertos=r.acertos, total=r.total)
            else:
                sim["i"] += 1
                question_card.definir_questao("sim_q", sim["qids"][sim["i"]])
            st.rerun()
    if st.button("Abandonar simulado"):
        st.session_state.pop("sim")
        st.rerun()


def render() -> None:
    st.title("Exercícios")
    modo = st.segmented_control("Modo de estudo", list(MODOS), format_func=lambda m: MODOS[m][0], key="ex_modo", default="treino") or "treino"
    st.caption(MODOS[modo][1])
    if modo == "simulado":
        _simulado()
    else:
        _treino(modo)
