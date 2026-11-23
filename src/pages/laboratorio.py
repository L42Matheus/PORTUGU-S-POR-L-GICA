"""Laboratório de Português: análise contextual de frases e textos."""

from __future__ import annotations

import streamlit as st

from src.app_state import aviso_ia_indisponivel, db, ia
from src.components import question_card, word_analyzer
from src.components.theme import legenda
from src.core.models import AnaliseTexto
from src.navigation import ir
from src.services import grammar_service, question_service
from src.services.ai_service import FalhaAnaliseIA

MODOS = {
    "morfologica": "Análise morfológica",
    "nomes": "Área dos Nomes",
    "verbos": "Área dos Verbos",
    "conectivos": "Área dos Conectivos",
    "completa": "Análise gramatical completa",
    "questoes": "Resolução de questões",
}
FOCO = {"nomes": "nomes", "verbos": "verbos", "conectivos": "conectivos"}
MAX_FRASES_IA = 12


def _executar(texto: str, modo: str) -> dict:
    """Analisa frase a frase: pré-validada quando houver; IA quando disponível; senão, pistas lexicais."""
    frases = grammar_service.segmentar_frases(texto)
    blocos, avisos, exercicios = [], [], []
    usados_ia = 0
    for fr in frases:
        pv = grammar_service.buscar_pre_validada(fr.texto)
        if pv is not None:
            blocos.append({"tipo": "analise", "base": fr.inicio, "analise": grammar_service.deslocar(pv, fr.inicio)})
            continue
        if ia().disponivel and usados_ia < MAX_FRASES_IA:
            usados_ia += 1
            try:
                r = ia().analisar_texto(fr.texto, modo)
                for a in r.frases:
                    blocos.append({"tipo": "analise", "base": fr.inicio, "analise": grammar_service.deslocar(a, fr.inicio)})
                avisos.extend(r.avisos)
                avisos.extend(f"Incerteza: {i}" for i in r.incertezas)
                if r.exercicio_fixacao:
                    exercicios.append(r.exercicio_fixacao)
                continue
            except FalhaAnaliseIA as exc:
                avisos.append(f"Frase “{fr.texto}”: {exc}")
        blocos.append({"tipo": "pistas", "frase": fr.texto, "pistas": grammar_service.pre_analise_lexical(fr.texto)})
    if ia().disponivel and len(frases) > MAX_FRASES_IA:
        avisos.append(f"Somente as primeiras {MAX_FRASES_IA} frases não validadas foram enviadas à IA.")
    return {"texto": texto, "modo": modo, "blocos": blocos, "avisos": avisos, "exercicios": exercicios}


def _origem(res: dict) -> str:
    tipos = {b["analise"].origem if b["tipo"] == "analise" else "lexical" for b in res["blocos"]}
    return tipos.pop() if len(tipos) == 1 else "misto"


def _salvar(res: dict) -> None:
    resultado = {
        "blocos": [
            b["analise"].model_dump() if b["tipo"] == "analise" else {"frase": b["frase"], "pistas": [p.__dict__ for p in b["pistas"]]}
            for b in res["blocos"]
        ],
        "avisos": res["avisos"],
    }
    with db() as s:
        s.add(AnaliseTexto(texto_original=res["texto"], modalidade=res["modo"], origem=_origem(res), resultado=resultado))


def render() -> None:
    st.title("Laboratório de Português")
    st.markdown("Cole uma frase, um parágrafo ou um trecho de prova. O texto original é preservado; nenhuma instrução contida nele é executada.")

    exemplos = [a.texto for a in grammar_service.carregar_analises()]
    with st.expander("Frases pré-validadas disponíveis (funcionam sem IA)"):
        escolhido = st.selectbox("Carregar exemplo", exemplos, index=None, placeholder="Escolha uma frase…")
        if escolhido and st.button("Usar esta frase"):
            st.session_state["lab_texto"] = escolhido
            st.session_state.pop("lab_res", None)
            st.rerun()

    with st.form("lab_form"):
        texto = st.text_area("Texto para análise", key="lab_texto", height=130, placeholder="Ex.: A menina inteligente respondeu rapidamente à questão.")
        modo = st.selectbox("Modo de análise", list(MODOS), format_func=MODOS.get, key="lab_modo")
        enviar = st.form_submit_button("Analisar", type="primary")

    if enviar:
        if not texto or not texto.strip():
            st.warning("Digite ou cole um texto antes de analisar.")
            st.session_state.pop("lab_res", None)
            return
        if modo == "questoes":
            st.session_state["rq_texto"] = texto
            ir("questoes")
        with st.spinner("Analisando…"):
            res = _executar(texto, modo)
        _salvar(res)
        st.session_state["lab_res"] = res

    res = st.session_state.get("lab_res")
    if not res:
        return

    st.divider()
    with st.expander("Legenda de cores das classes"):
        st.markdown(legenda(), unsafe_allow_html=True)

    tem_pistas = any(b["tipo"] == "pistas" for b in res["blocos"])
    if tem_pistas and not ia().disponivel:
        aviso_ia_indisponivel()

    for i, b in enumerate(res["blocos"]):
        if b["tipo"] == "analise":
            st.subheader(f"Frase {i + 1}")
            word_analyzer.render_analise(b["analise"], chave=f"lab_{i}", foco_area=FOCO.get(res["modo"]), base=b["base"])
        else:
            st.subheader(f"Frase {i + 1}: “{b['frase']}”")
            st.markdown(
                "Esta frase **não está no banco de análises revisadas** e a análise contextual precisa da IA. "
                "Abaixo, apenas as **classes possíveis** de palavras de classe fechada e as contrações identificadas — "
                "isto **não é** uma classificação."
            )
            word_analyzer.render_pistas(b["pistas"])

    for a in res["avisos"]:
        st.caption(f"⚠ {a}")

    analises = [b["analise"] for b in res["blocos"] if b["tipo"] == "analise"]
    if analises:
        st.divider()
        st.subheader("Fixação")
        assunto = analises[0].assunto_principal
        if res["exercicios"]:
            ex = res["exercicios"][0]
            st.caption("Exercício gerado pela IA (não revisado):")
            st.markdown(f"**{ex.enunciado}**")
            escolha = st.radio("Alternativas", [a.letra for a in ex.alternativas], index=None, format_func=lambda letra: next(f"{a.letra}) {a.texto}" for a in ex.alternativas if a.letra == letra), key="lab_ex_ia")
            if escolha:
                (st.success if escolha == ex.resposta else st.error)(f"Resposta sugerida: {ex.resposta}. {ex.justificativa}")
        chave = "lab_fix"
        if st.session_state.get("lab_fix_assunto") != assunto:
            st.session_state["lab_fix_assunto"] = assunto
            with db() as s:
                q = question_service.sortear(question_service.filtrar(assunto=assunto), s)
            question_card.definir_questao(chave, q.id if q else None)
        if question_card.questao_atual(chave):
            st.caption("Questão revisada do banco sobre o mesmo assunto:")
            question_card.render(chave, modo="laboratorio")
