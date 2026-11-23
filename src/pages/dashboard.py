"""Desempenho: estatísticas derivadas das respostas registradas."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from src.app_state import db
from src.components import progress_chart
from src.services import revision_service, stats_service
from src.services.content_service import carregar_areas, mapa_assuntos, nome_assunto

PERIODOS = {"tudo": "Todo o período", "7": "Últimos 7 dias", "30": "Últimos 30 dias", "90": "Últimos 90 dias"}
DIFS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}


def render() -> None:
    st.title("Desempenho")
    st.caption("Todas as métricas derivam das respostas efetivamente registradas. Não há índice artificial de domínio.")

    areas = carregar_areas()
    c1, c2, c3, c4 = st.columns(4)
    area = c1.selectbox("Área", [None] + [a.id for a in areas], format_func=lambda i: "Todas" if i is None else next(a.nome for a in areas if a.id == i))
    assuntos = [k for k, (a, _) in mapa_assuntos().items() if area is None or a.id == area]
    assunto = c2.selectbox("Assunto", [None] + assuntos, format_func=lambda i: "Todos" if i is None else nome_assunto(i))
    periodo = c3.selectbox("Período", list(PERIODOS), format_func=PERIODOS.get)
    dif = c4.selectbox("Dificuldade", [None, *DIFS], format_func=lambda d: "Todas" if d is None else DIFS[d])
    desde = None if periodo == "tudo" else date.today() - timedelta(days=int(periodo) - 1)

    with db() as s:
        bruto = stats_service.tentativas_df(s)
        n_pend = len(revision_service.pendentes(s))
        sims = stats_service.historico_simulados(s)
    df = stats_service.filtrar(bruto, area=area, assunto=assunto, dificuldade=dif, desde=desde)
    r = stats_service.resumo(df)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Questões resolvidas", r.resolvidas)
    m2.metric("Acertos", f"{r.taxa:.0%}" if r.taxa is not None else "—", help=f"{r.acertos} de {r.avaliadas} avaliadas")
    m3.metric("Tempo de estudo", f"{r.tempo_total_min:.0f} min", help="Soma do tempo de resposta registrado")
    m4.metric("Revisões pendentes", n_pend)
    m5.metric("Sequência de dias", stats_service.sequencia(bruto))
    if r.pendentes_avaliacao:
        st.caption(f"{r.pendentes_avaliacao} justificativa(s) aguardando autoavaliação não entram na taxa de acertos.")

    if df.empty:
        st.info("Sem respostas registradas para esses filtros. Resolva exercícios para ver seus gráficos.")
        return

    g1, g2 = st.columns(2)
    with g1:
        pa = stats_service.por_area(df)
        if not pa.empty:
            st.plotly_chart(progress_chart.barras_taxa(pa, "Acertos por área"), use_container_width=True)
    with g2:
        sem = stats_service.evolucao_semanal(df)
        if not sem.empty:
            st.plotly_chart(progress_chart.linha_semanal(sem), use_container_width=True)

    g3, g4 = st.columns(2)
    with g3:
        dific = stats_service.assuntos_dificeis(df)
        if not dific.empty:
            st.plotly_chart(progress_chart.barras_taxa(dific, "Assuntos com maior dificuldade"), use_container_width=True)
    with g4:
        nv = stats_service.por_dificuldade(df)
        if not nv.empty:
            st.plotly_chart(progress_chart.barras_taxa(nv, "Desempenho por nível"), use_container_width=True)

    st.subheader("Histórico de simulados")
    if sims.empty:
        st.caption("Nenhum simulado concluído.")
    else:
        st.plotly_chart(progress_chart.linha_simulados(sims), use_container_width=True)
        st.dataframe(
            sims.assign(data=sims["data"].dt.strftime("%d/%m/%Y %H:%M"), taxa=sims["taxa"].map(lambda t: f"{t:.0%}" if t is not None else "—")),
            hide_index=True,
            use_container_width=True,
        )
