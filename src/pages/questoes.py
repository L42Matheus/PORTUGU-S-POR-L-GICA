"""Resolver Questão (resolução comentada) e Aprender Raciocinando (tutor socrático)."""

from __future__ import annotations

import random

import streamlit as st

from src.app_state import aviso_ia_indisponivel, ia
from src.components import question_card
from src.components.theme import rotulo
from src.core.schemas import CLASSES, QuestaoSchema, RoteiroTutor
from src.services import question_parser, question_service
from src.services.ai_service import FalhaAnaliseIA
from src.services.content_service import carregar_roteiros, nome_assunto, questao_por_id

EXEMPLO = questao_por_id("C17")


def _texto_exemplo(q: QuestaoSchema) -> str:
    partes = [q.texto_base] if q.texto_base else []
    partes.append(q.enunciado)
    partes += [f"{a.letra}) {a.texto}" for a in q.alternativas]
    return "\n".join(partes)


# --------------------------------------------------------------------------- #
# Resolução comentada
# --------------------------------------------------------------------------- #


def _resolucao_banco(p: question_parser.QuestaoParseada, q: QuestaoSchema) -> None:
    st.success(f"Esta questão corresponde à questão revisada **{q.id}** do banco do app. A resolução abaixo é revisada.")
    st.markdown("#### Etapa 4 — Construir o raciocínio")
    st.markdown(f"**Regra aplicada:** {q.regra}")
    st.markdown(q.justificativa)
    st.markdown("#### Etapa 5 — Analisar cada alternativa")
    for a in q.alternativas:
        if a.letra == q.resposta:
            st.markdown(f"**{a.letra})** {a.texto} — ✔ É a alternativa que atende ao comando. {q.justificativa}")
        else:
            st.markdown(f"**{a.letra})** {a.texto} — ✘ Não atende ao comando. {a.comentario or ''}")
    st.markdown("#### Etapa 6 — Gabarito")
    alt = q.alternativa(q.resposta)
    st.markdown(f"**{q.resposta}) {alt.texto if alt else ''}**")
    st.caption("Gabarito do banco revisado deste aplicativo — não é gabarito oficial de banca.")
    st.markdown("#### Etapa 7 — Fixação")
    prox = question_service.semelhante(q)
    if prox:
        if st.session_state.get("rq_fix_base") != q.id:
            st.session_state["rq_fix_base"] = q.id
            question_card.definir_questao("rq_fix", prox.id)
        question_card.render("rq_fix", modo="resolver")


def _resolucao_ia(p: question_parser.QuestaoParseada) -> None:
    try:
        with st.spinner("Construindo a resolução…"):
            r = ia().resolver_questao(p)
    except FalhaAnaliseIA as exc:
        st.error(f"Não foi possível concluir a resolução: {exc}")
        return
    st.warning("Resolução **sugerida por IA**. Confira o raciocínio; não se trata de gabarito oficial.")
    st.markdown(f"**Assunto (IA):** {r.assunto}")
    st.markdown(f"**Comando (IA):** {r.comando_interpretado}")
    if r.elementos_relevantes:
        st.markdown("**Elementos relevantes:** " + ", ".join(f"*{e}*" for e in r.elementos_relevantes))
    st.markdown("#### Etapa 4 — Construir o raciocínio")
    for i, passo in enumerate(r.raciocinio, 1):
        st.markdown(f"{i}. {passo}")
    st.markdown("#### Etapa 5 — Analisar cada alternativa")
    icone = {"correta": "✔", "incorreta": "✘", "indeterminada": "?"}
    for a in r.alternativas:
        st.markdown(f"**{a.letra})** {icone[a.avaliacao]} {a.explicacao}")
    st.markdown("#### Etapa 6 — Gabarito sugerido")
    if r.gabarito_sugerido:
        st.markdown(f"**{r.gabarito_sugerido}** — {r.justificativa_gabarito}")
    else:
        st.markdown("Não foi possível determinar o gabarito com segurança.")
    for inc in r.incertezas:
        st.caption(f"Incerteza: {inc}")
    for av in r.avisos:
        st.caption(f"⚠ {av}")
    st.markdown("#### Etapa 7 — Fixação")
    st.markdown(r.questao_fixacao)


def _aba_resolver() -> None:
    st.markdown("Cole o texto-base, o enunciado e as alternativas (uma por linha: `A) ...`).")
    if EXEMPLO and st.button("Carregar questão de exemplo"):
        st.session_state["rq_texto"] = _texto_exemplo(EXEMPLO)
    with st.form("rq_form"):
        texto = st.text_area("Questão", key="rq_texto", height=220)
        enviar = st.form_submit_button("Resolver passo a passo", type="primary")
    if enviar:
        st.session_state["rq_ativo"] = texto
    alvo = st.session_state.get("rq_ativo")
    if not alvo:
        return
    try:
        p = question_parser.interpretar(alvo)
    except ValueError as exc:
        st.warning(str(exc))
        return

    st.markdown("#### Etapa 1 — Identificar o assunto")
    st.markdown(question_parser.descrever_assuntos(p))
    st.markdown("#### Etapa 2 — Interpretar o comando")
    st.markdown(p.comando_explicacao)
    st.markdown("#### Etapa 3 — Localizar os elementos")
    st.markdown(f"**Enunciado:** {p.enunciado}")
    for a in p.alternativas:
        st.markdown(f"- **{a.letra})** {a.texto}")
    for av in p.avisos:
        st.caption(f"⚠ {av}")

    q = question_parser.buscar_no_banco(p)
    if q is not None and q.alternativas:
        _resolucao_banco(p, q)
    elif ia().disponivel:
        _resolucao_ia(p)
    else:
        aviso_ia_indisponivel()
        st.markdown(
            "As etapas 1 a 3 acima foram feitas sem IA. A resolução comentada completa (etapas 4 a 7) "
            "está disponível para as questões do banco revisado; para outras questões, configure a IA. "
            "Experimente também a aba **Aprender raciocinando**."
        )


# --------------------------------------------------------------------------- #
# Tutor socrático
# --------------------------------------------------------------------------- #


def _estado() -> dict:
    return st.session_state.setdefault("tutor", {"id": None, "fase": "inicial", "passo": 0, "msgs": []})


def _reiniciar(rid: str) -> None:
    st.session_state["tutor"] = {"id": rid, "fase": "inicial", "passo": 0, "msgs": []}


def _opcoes_iniciais(r: RoteiroTutor) -> tuple[list[str], str]:
    if r.opcoes_iniciais:
        opcoes, correta = list(r.opcoes_iniciais), r.opcoes_iniciais[0]
    else:
        opcoes, correta = [rotulo(c) for c in CLASSES], rotulo(r.classe_correta)
    random.Random(r.id).shuffle(opcoes)
    return opcoes, correta


def _aba_tutor() -> None:
    st.markdown("O tutor **não revela a resposta de imediato**: você responde, e ele conduz o raciocínio com perguntas.")
    roteiros = carregar_roteiros()
    est = _estado()
    rid = st.selectbox("Escolha um desafio", [r.id for r in roteiros], format_func=lambda i: next(f"“{r.frase}” — {r.alvo}" for r in roteiros if r.id == i))
    if est["id"] != rid:
        _reiniciar(rid)
        est = _estado()
    r = next(x for x in roteiros if x.id == rid)

    st.markdown(f"### {r.frase}")
    for papel, msg in est["msgs"]:
        with st.chat_message("assistant" if papel == "tutor" else "user"):
            st.markdown(msg)

    if est["fase"] == "inicial":
        opcoes, correta = _opcoes_iniciais(r)
        with st.chat_message("assistant"):
            st.markdown(r.pergunta_inicial)
        with st.form(f"tut_ini_{rid}"):
            esc = st.radio("Sua resposta", opcoes, index=None)
            ok = st.form_submit_button("Responder")
        if ok and esc:
            est["msgs"] += [("tutor", r.pergunta_inicial), ("aluno", esc)]
            if esc == correta:
                est["msgs"].append(("tutor", "Boa! Mas acertar a classe não basta: **por que** essa é a classificação?"))
                est["fase"] = "justificativa"
            else:
                est["msgs"].append(("tutor", "Ainda não. Vamos investigar juntos, passo a passo."))
                est["fase"] = "passos"
            st.rerun()

    elif est["fase"] == "justificativa":
        textos = [o.texto for o in r.justificativas]
        random.Random(r.id + "j").shuffle(textos)
        with st.form(f"tut_just_{rid}"):
            esc = st.radio("Escolha a justificativa", textos, index=None)
            ok = st.form_submit_button("Responder")
        if ok and esc:
            op = next(o for o in r.justificativas if o.texto == esc)
            est["msgs"].append(("aluno", esc))
            est["msgs"].append(("tutor", op.retorno))
            if op.correta:
                est["fase"] = "fim"
            else:
                est["msgs"].append(("tutor", "Sua classificação coincidiu com a esperada, mas a justificativa não se sustenta. Vamos refazer o raciocínio."))
                est["fase"] = "passos"
            st.rerun()

    elif est["fase"] == "passos":
        passo = r.passos[est["passo"]]
        with st.chat_message("assistant"):
            st.markdown(f"**Passo {est['passo'] + 1}/{len(r.passos)}:** {passo.pergunta}")
        textos = [o.texto for o in passo.opcoes]
        random.Random(f"{r.id}{est['passo']}").shuffle(textos)
        with st.form(f"tut_p_{rid}_{est['passo']}"):
            esc = st.radio("Sua resposta", textos, index=None)
            ok = st.form_submit_button("Responder")
        if ok and esc:
            op = next(o for o in passo.opcoes if o.texto == esc)
            est["msgs"] += [("tutor", passo.pergunta), ("aluno", esc), ("tutor", ("✔ " if op.correta else "✘ ") + op.retorno)]
            if op.correta:
                est["passo"] += 1
                if est["passo"] >= len(r.passos):
                    est["fase"] = "fim"
            st.rerun()

    if est["fase"] == "fim":
        st.success(f"**Conclusão:** {r.conclusao}")
        st.info(f"**Contraexemplo:** {r.contraexemplo}")
        if st.button("Recomeçar este desafio"):
            _reiniciar(rid)
            st.rerun()
    elif st.button("Mostrar resposta", help="Encerra o processo guiado"):
        est["fase"] = "fim"
        st.rerun()
    st.caption(f"Assunto: {nome_assunto(r.assunto)}")


def render() -> None:
    st.title("Resolver Questões")
    t1, t2 = st.tabs(["Resolução comentada", "Aprender raciocinando (tutor)"])
    with t1:
        _aba_resolver()
    with t2:
        _aba_tutor()
