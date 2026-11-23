"""Visualização interativa de uma análise de frase."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.core.schemas import ROTULO_EXPRESSAO, AnaliseFrase, Elemento
from src.components.theme import CLASSES_POR_AREA, CORES, SIGLAS, rotulo
from src.services.content_service import nome_assunto
from src.services.grammar_service import PistaLexical

ROTULO_CONF = {"alta": "alta", "media": "média", "baixa": "baixa"}


def _chip(texto: str, classe: str, destacado: bool = True) -> str:
    cor = CORES.get(classe, "#374151")
    sigla = SIGLAS.get(classe, classe.upper())
    t = html.escape(texto)
    dim = "" if destacado else " dim"
    return (
        f'<span class="ppl-chip{dim}" style="--c:{cor}" role="note" aria-label="{t}: {html.escape(rotulo(classe))}">'
        f'<span class="w">{t}</span><span class="t">{sigla}</span></span>'
    )


def frase_colorida(analise: AnaliseFrase, foco_area: str | None = None, base: int = 0) -> str:
    """Reconstrói a frase original com chips nas posições dos elementos."""
    texto = analise.texto
    foco = CLASSES_POR_AREA.get(foco_area or "", None)
    partes, cursor = [], 0
    for el in sorted(analise.elementos, key=lambda e: e.inicio):
        ini, fim = el.inicio - base, el.fim - base
        if ini > cursor:
            partes.append(f'<span class="ppl-plain">{html.escape(texto[cursor:ini])}</span>')
        partes.append(_chip(texto[ini:fim], el.classe, foco is None or el.classe in foco))
        cursor = fim
    if cursor < len(texto):
        partes.append(f'<span class="ppl-plain">{html.escape(texto[cursor:])}</span>')
    return f'<div class="ppl-frase">{"".join(partes)}</div>'


def _descricao_classe(el: Elemento) -> str:
    if el.classe == "contracao":
        return "Contração: " + " + ".join(f"{c.texto} ({rotulo(c.classe)})" for c in el.componentes)
    return rotulo(el.classe) + (f" — {el.subtipo}" if el.subtipo else "")


def _painel_elemento(analise: AnaliseFrase, el: Elemento) -> None:
    with st.container(border=True):
        st.markdown(f"#### “{el.texto}”")
        st.markdown(f"**Classe (morfologia):** {_descricao_classe(el)}")
        if el.relacao:
            alvo = analise.elemento(el.relacionado_a)
            st.markdown(f"**Relação:** {el.relacao}" + (f" → *{alvo.texto}*" if alvo and alvo.texto not in el.relacao else ""))
        st.markdown(f"**Por quê:** {el.justificativa}")
        if el.funcao_sintatica:
            st.markdown(f"**Nível sintático (função, não classe):** {el.funcao_sintatica}")
        st.caption(f"Confiança qualitativa: {ROTULO_CONF[el.confianca]}")
        for alt in el.classificacoes_alternativas:
            st.markdown(f"↔ Seria **{rotulo(alt.classe)}** {alt.condicao}.")


def diagrama(analise: AnaliseFrase) -> str:
    linhas = [
        "digraph G {",
        'rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fontname="Helvetica", fontcolor="white"]; edge [fontname="Helvetica", fontsize=10];',
    ]

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    em_expr = {}
    for x in analise.expressoes:
        for i in x.elementos:
            em_expr[i] = x
    for x in analise.expressoes:
        linhas.append(f'subgraph cluster_{x.id} {{ label="{esc(ROTULO_EXPRESSAO[x.tipo])}"; style=dashed; fontname="Helvetica";')
        for el in analise.elementos:
            if el.id in x.elementos:
                linhas.append(f'"{el.id}" [label="{esc(el.texto)}\\n{esc(rotulo(el.classe))}", fillcolor="{CORES.get(el.classe, "#374151")}"];')
        linhas.append("}")
    for el in analise.elementos:
        if el.id not in em_expr:
            linhas.append(f'"{el.id}" [label="{esc(el.texto)}\\n{esc(rotulo(el.classe))}", fillcolor="{CORES.get(el.classe, "#374151")}"];')
    for el in analise.elementos:
        if el.relacionado_a:
            verbo = (el.relacao or "").split(" ")[0]
            linhas.append(f'"{el.id}" -> "{el.relacionado_a}" [label="{esc(verbo)}"];')
    for x in analise.expressoes:
        if x.relacionado_a and x.elementos:
            linhas.append(f'"{x.elementos[-1]}" -> "{x.relacionado_a}" [label="{esc(x.subtipo or "valor")}", style=bold, ltail="cluster_{x.id}"];')
    linhas.append("}")
    return "\n".join(linhas)


def render_analise(analise: AnaliseFrase, chave: str, foco_area: str | None = None, base: int = 0) -> None:
    origem = "Análise pré-validada (revisada)" if analise.origem == "pre_validada" else "Análise sugerida por IA — confira o raciocínio"
    st.caption(f"{origem} · Assunto principal: {nome_assunto(analise.assunto_principal)}")
    st.markdown(frase_colorida(analise, foco_area, base), unsafe_allow_html=True)

    opcoes = list(range(len(analise.elementos)))
    escolha = st.pills(
        "Clique em uma palavra para ver a classificação e a explicação:",
        opcoes,
        format_func=lambda i: f"{analise.elementos[i].texto} · {SIGLAS.get(analise.elementos[i].classe, '')}",
        key=f"{chave}_pill",
        selection_mode="single",
    )
    if escolha is not None:
        _painel_elemento(analise, analise.elementos[escolha])

    st.markdown(f'<div class="ppl-box">{html.escape(analise.explicacao)}</div>', unsafe_allow_html=True)

    tab_tab, tab_rel, tab_niv = st.tabs(["Tabela", "Diagrama de relações", "Morfologia × sintaxe"])
    with tab_tab:
        df = pd.DataFrame(
            [
                {
                    "Elemento": e.texto,
                    "Classe": _descricao_classe(e),
                    "Relação": e.relacao or "—",
                    "Confiança": ROTULO_CONF[e.confianca],
                }
                for e in analise.elementos
            ]
        )
        st.dataframe(df, hide_index=True, use_container_width=True)
        if analise.expressoes:
            st.markdown("**Expressões (locuções não são classes: cada palavra mantém sua classe):**")
            for x in analise.expressoes:
                alvo = analise.elemento(x.relacionado_a)
                st.markdown(
                    f"- **{x.texto}** — {ROTULO_EXPRESSAO[x.tipo]}"
                    + (f" de {x.subtipo}" if x.subtipo and x.tipo in {"locucao_adverbial", "expressao_adverbial"} else (f" ({x.subtipo})" if x.subtipo else ""))
                    + (f", ligada a *{alvo.texto}*" if alvo else "")
                    + f". {x.justificativa}"
                )
    with tab_rel:
        st.graphviz_chart(diagrama(analise), use_container_width=True)
        st.caption("Setas apontam do elemento para o termo a que ele se relaciona.")
    with tab_niv:
        st.markdown("**Nível morfológico** — a classe de cada palavra (o que ela é). **Nível sintático** — a função que exerce na oração (o que ela faz).")
        if analise.nivel_sintatico:
            for n in analise.nivel_sintatico:
                st.markdown(f"- {n}")
        else:
            st.caption("Sem observações sintáticas para esta frase.")

    if analise.ambiguidades:
        for a in analise.ambiguidades:
            st.warning(f"Ambiguidade / divergência: {a}")
    if analise.comparacoes:
        with st.expander("Compare com outros contextos"):
            for c in analise.comparacoes:
                st.markdown(f"- *{c.frase}* — {c.explicacao}")
    for aviso in analise.avisos:
        st.caption(f"⚠ {aviso}")


def render_pistas(pistas: list[PistaLexical]) -> None:
    """Exibe a pré-análise lexical, sem classificar palavras de classe aberta."""
    linhas = []
    for p in pistas:
        if p.componentes:
            poss = p.observacao
        elif p.possibilidades:
            poss = " | ".join(f"{rotulo(c)}: {o}" for c, o in p.possibilidades)
        else:
            poss = p.observacao
        linhas.append({"Palavra": p.texto, "Classes possíveis (sem análise de contexto)": poss})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
