"""Revisões: revisão espaçada por assunto e "Revisar meus erros"."""

from __future__ import annotations

import streamlit as st

from src.app_state import db
from src.components import question_card
from src.services import question_service, revision_service
from src.services.content_service import nome_assunto, questao_por_id


def render() -> None:
    st.title("Revisões")
    t1, t2, t3 = st.tabs(["Revisão espaçada", "Revisar meus erros", "Agenda completa"])

    with db() as s:
        pend = [(r.assunto_id, r.proxima_data, r.intervalo, r.desempenho, r.acertos + r.erros) for r in revision_service.pendentes(s)]
        agenda = [(r.assunto_id, r.proxima_data, r.intervalo, r.desempenho, r.acertos, r.erros, r.ultima_revisao) for r in revision_service.todas(s)]
        erros = [(q.id, t.resposta_usuario, t.data) for q, t in question_service.questoes_com_erro_pendente(s)]
        aval = [(t.id, t.questao_id, t.resposta_usuario) for t in question_service.tentativas_pendentes_avaliacao(s)]

    with t1:
        st.caption("Intervalos: 1 → 3 → 7 → 15 → 30 dias após acertos; um erro traz o assunto de volta para o dia seguinte.")
        if not pend:
            st.success("Nenhum assunto com revisão pendente hoje.")
        else:
            assunto = st.radio(
                "Assuntos para revisar hoje",
                [p[0] for p in pend],
                format_func=lambda a: next(f"{nome_assunto(a)} — acertos {d:.0%} em {n} tentativa(s)" for x, _, _, d, n in pend if x == a),
            )
            chave = "rev_esp"
            if st.session_state.get("rev_esp_assunto") != assunto or st.button("Outra questão"):
                st.session_state["rev_esp_assunto"] = assunto
                with db() as s:
                    q = question_service.sortear(question_service.filtrar(assunto=assunto), s)
                question_card.definir_questao(chave, q.id if q else None)
            question_card.render(chave, modo="revisao")

    with t2:
        if not erros:
            st.success("Nenhuma questão com erro pendente. Questões cuja última resposta foi incorreta aparecem aqui.")
        else:
            st.markdown(f"**{len(erros)}** questão(ões) com a última resposta incorreta.")
            for qid, resp, data in erros:
                q = questao_por_id(qid)
                with st.container(border=True):
                    st.markdown(f"**{qid}** · {nome_assunto(q.assunto)} — {q.enunciado}")
                    st.caption(f"Sua última resposta: {resp} · {data:%d/%m/%Y %H:%M}")
                    c1, c2 = st.columns(2)
                    if c1.button("Refazer a mesma questão", key=f"refazer_{qid}"):
                        question_card.definir_questao("rev_erro", qid)
                    if c2.button("Tentar uma variação", key=f"var_{qid}", help="Mesma regra, outra frase"):
                        with db() as s:
                            v = question_service.semelhante(q, s)
                        question_card.definir_questao("rev_erro", v.id if v else qid)
            if question_card.questao_atual("rev_erro"):
                st.divider()
                question_card.render("rev_erro", modo="erros")
        if aval:
            st.divider()
            st.markdown(f"**Justificativas aguardando autoavaliação:** {len(aval)}")
            for tid, qid, resp in aval:
                st.caption(f"{qid}: “{resp[:120]}”")

    with t3:
        if not agenda:
            st.caption("A agenda é criada conforme você responde questões.")
        else:
            st.dataframe(
                [
                    {
                        "Assunto": nome_assunto(a),
                        "Próxima revisão": p.strftime("%d/%m/%Y"),
                        "Intervalo (dias)": i,
                        "Taxa de acertos": f"{d:.0%}",
                        "Acertos": ac,
                        "Erros": er,
                        "Última revisão": u.strftime("%d/%m/%Y") if u else "—",
                    }
                    for a, p, i, d, ac, er, u in agenda
                ],
                hide_index=True,
                use_container_width=True,
            )
