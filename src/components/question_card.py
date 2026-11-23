"""Cartão interativo de questão: resposta, correção, feedback e registro."""

from __future__ import annotations

import random
import time

import streamlit as st

from src.app_state import db, ia
from src.core.schemas import QuestaoSchema
from src.services import feedback_service, question_service
from src.services.ai_service import FalhaAnaliseIA
from src.services.content_service import nome_assunto, questao_por_id

ROTULO_DIF = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}
ROTULO_TIPO = {
    "multipla_escolha": "Múltipla escolha",
    "verdadeiro_falso": "Verdadeiro ou falso",
    "associacao": "Associação",
    "identificar_palavra": "Identificar palavra",
    "identificar_classe": "Identificar classe",
    "completar": "Completar",
    "identificar_relacao": "Identificar relação",
    "encontrar_erro": "Encontrar o erro",
    "comparar": "Comparar contextos",
    "justificativa": "Justificar com texto livre",
}


def definir_questao(chave: str, qid: str | None) -> None:
    st.session_state[f"{chave}_qid"] = qid
    for suf in ("_res", "_inicio", "_tid"):
        st.session_state.pop(f"{chave}{suf}", None)


def questao_atual(chave: str) -> QuestaoSchema | None:
    qid = st.session_state.get(f"{chave}_qid")
    return questao_por_id(qid) if qid else None


def _texto_base(q: QuestaoSchema) -> None:
    if not q.texto_base:
        return
    texto = q.texto_base
    if q.destaque:
        texto = texto.replace(q.destaque, f"**{q.destaque}**", 1)
    st.markdown("\n\n".join(f"> {linha}" for linha in texto.split("\n")))


def render(chave: str, modo: str = "treino", simulado_id: int | None = None, permitir_semelhante: bool = True) -> dict | None:
    """Renderiza a questão corrente de ``chave``. Devolve o resultado quando respondida."""
    q = questao_atual(chave)
    if q is None:
        return None
    st.session_state.setdefault(f"{chave}_inicio", time.monotonic())

    with st.container(border=True):
        st.caption(f"{q.id} · {nome_assunto(q.assunto)} · {ROTULO_DIF[q.dificuldade]} · {ROTULO_TIPO[q.tipo]}")
        _texto_base(q)
        st.markdown(f"**{q.enunciado}**")

        resultado = st.session_state.get(f"{chave}_res")
        if resultado is None:
            _formulario(q, chave, modo, simulado_id)
        else:
            _mostrar_feedback(q, chave, resultado)
            if permitir_semelhante and modo != "simulado":
                prox = question_service.semelhante(q)
                if prox and st.button("Nova questão semelhante", key=f"{chave}_sem", help="Mesma regra, outro contexto"):
                    definir_questao(chave, prox.id)
                    st.rerun()
    return st.session_state.get(f"{chave}_res")


def _formulario(q: QuestaoSchema, chave: str, modo: str, simulado_id: int | None) -> None:
    with st.form(f"{chave}_form_{q.id}"):
        resposta = None
        if q.tipo == "associacao":
            opcoes = sorted({p.resposta for p in q.pares})
            random.Random(q.id).shuffle(opcoes)
            resposta = {}
            for i, p in enumerate(q.pares):
                resposta[p.item] = st.selectbox(p.item, opcoes, index=None, placeholder="Escolha…", key=f"{chave}_{q.id}_a{i}")
        elif q.tipo == "justificativa":
            resposta = st.text_area("Sua justificativa", key=f"{chave}_{q.id}_txt", height=120)
        else:
            resposta = st.radio(
                "Alternativas",
                q.letras,
                index=None,
                format_func=lambda letra: f"{letra}) {q.alternativa(letra).texto}",
                key=f"{chave}_{q.id}_radio",
                label_visibility="collapsed",
            )
        enviado = st.form_submit_button("Responder", type="primary")

    if not enviado:
        return
    if resposta is None or (isinstance(resposta, dict) and None in resposta.values()) or (isinstance(resposta, str) and not resposta.strip()):
        st.warning("Responda antes de enviar.")
        return

    correcao = question_service.corrigir(q, resposta)
    tempo = time.monotonic() - st.session_state.get(f"{chave}_inicio", time.monotonic())
    avaliacao_ia = None
    if q.tipo == "justificativa" and ia().disponivel:
        try:
            with st.spinner("Avaliando seu raciocínio…"):
                avaliacao_ia = ia().avaliar_justificativa(q, resposta)
            correcao.correta = avaliacao_ia.veredito == "adequada"
        except FalhaAnaliseIA as exc:
            st.warning(f"Não foi possível avaliar por IA: {exc} Use a autoavaliação abaixo.")

    with db() as s:
        t = question_service.registrar_tentativa(s, q, correcao.resposta_registrada, correcao.correta, tempo, modo, simulado_id)
        tid = t.id
    fb = feedback_service.gerar(q, correcao)
    if correcao.correta is not None:
        fb.correta = correcao.correta
    st.session_state[f"{chave}_tid"] = tid
    st.session_state[f"{chave}_res"] = {"feedback": fb, "ia": avaliacao_ia, "correta": correcao.correta}
    st.rerun()


def _mostrar_feedback(q: QuestaoSchema, chave: str, res: dict) -> None:
    fb: feedback_service.Feedback = res["feedback"]
    aval = res.get("ia")

    if q.tipo == "justificativa":
        if aval is not None:
            cor = {"adequada": st.success, "parcial": st.warning, "inadequada": st.error}[aval.veredito]
            cor(f"Avaliação sugerida pela IA: **{aval.veredito}**. {aval.comentario}")
            for p in aval.pontos_corretos:
                st.markdown(f"✔ {p}")
            for p in aval.problemas:
                st.markdown(f"✘ {p}")
        st.markdown("**Resposta modelo (revisada):**")
        st.info(fb.explicacao)
        st.caption(fb.observacao or "")
        if res.get("correta") is None:
            st.markdown("Compare com a resposta modelo e registre sua autoavaliação:")
            c1, c2 = st.columns(2)
            if c1.button("Meu raciocínio estava correto", key=f"{chave}_ok"):
                _autoavaliar(chave, True)
            if c2.button("Meu raciocínio estava incorreto", key=f"{chave}_nok"):
                _autoavaliar(chave, False)
        st.markdown(f"**Regra:** {fb.regra}")
        return

    if fb.correta:
        st.success(f"**{fb.titulo}** Você marcou {fb.escolhida}." if fb.escolhida else f"**{fb.titulo}**")
    else:
        st.error(f"**{fb.titulo}.** Você marcou {fb.escolhida}. Resposta correta: {fb.resposta_correta}." if fb.escolhida else f"**{fb.titulo}.** Gabarito: {fb.resposta_correta}")
        if fb.diagnostico:
            st.markdown(f"**O que aconteceu:** {fb.diagnostico}")
    if fb.detalhes_associacao:
        st.markdown(" · ".join(f"{'✔' if ok else '✘'} {i}" for i, ok in fb.detalhes_associacao.items()))
    st.markdown(f"**Explicação:** {fb.explicacao}")
    st.markdown(f"**Regra aplicada:** {fb.regra}")
    if fb.observacao:
        st.caption(fb.observacao)
    if not fb.correta and fb.exemplos:
        st.markdown("**Exemplo diferente:** " + fb.exemplos[0])


def _autoavaliar(chave: str, correta: bool) -> None:
    tid = st.session_state.get(f"{chave}_tid")
    if tid is None:
        return
    with db() as s:
        question_service.avaliar_tentativa(s, tid, correta)
    st.session_state[f"{chave}_res"]["correta"] = correta
    st.rerun()
