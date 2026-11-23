"""Identidade visual das classes e preferências de acessibilidade."""

from __future__ import annotations

import streamlit as st

from src.core.schemas import ROTULO_CLASSE

# Cores escolhidas para contraste ≥ 4.5:1 com texto branco. Cada classe
# também tem uma sigla textual, para não depender só da cor.
CORES: dict[str, str] = {
    "substantivo": "#1d4ed8",
    "adjetivo": "#15803d",
    "artigo": "#4b5563",
    "pronome": "#7c3aed",
    "numeral": "#a16207",
    "verbo": "#b91c1c",
    "adverbio": "#c2410c",
    "preposicao": "#0e7490",
    "conjuncao": "#be185d",
    "interjeicao": "#4d7c0f",
    "contracao": "#0f766e",
}

SIGLAS: dict[str, str] = {
    "substantivo": "SUBST",
    "adjetivo": "ADJ",
    "artigo": "ART",
    "pronome": "PRON",
    "numeral": "NUM",
    "verbo": "VERBO",
    "adverbio": "ADV",
    "preposicao": "PREP",
    "conjuncao": "CONJ",
    "interjeicao": "INTERJ",
    "contracao": "PREP+ART",
}

CLASSES_POR_AREA: dict[str, set[str]] = {
    "nomes": {"substantivo", "adjetivo", "artigo", "pronome", "numeral"},
    "verbos": {"verbo", "adverbio"},
    "conectivos": {"preposicao", "conjuncao", "contracao"},
    "complementares": {"interjeicao"},
}


def rotulo(classe: str) -> str:
    return ROTULO_CLASSE.get(classe, classe)


def aplicar_preferencias() -> None:
    """Injeta CSS conforme as preferências de acessibilidade da sessão."""
    escala = st.session_state.get("pref_fonte", 100) / 100
    alto = st.session_state.get("pref_contraste", False)
    css = f"""
    <style>
    html, body, [class*="css"], .stMarkdown, .stRadio, .stTextArea textarea {{
        font-size: {escala:.2f}rem;
    }}
    .ppl-frase {{ line-height: 2.6; font-size: {1.15 * escala:.2f}rem; }}
    .ppl-chip {{
        display: inline-flex; flex-direction: column; align-items: center;
        margin: 0 .18rem .35rem 0; padding: .15rem .45rem; border-radius: .45rem;
        background: var(--c); color: #fff; line-height: 1.15; vertical-align: top;
    }}
    .ppl-chip .w {{ font-weight: 600; }}
    .ppl-chip .t {{ font-size: .62em; letter-spacing: .04em; opacity: .95; }}
    .ppl-chip.dim {{ opacity: .35; }}
    .ppl-plain {{ margin-right: .18rem; }}
    .ppl-legenda span.ppl-chip {{ flex-direction: row; gap: .3rem; }}
    .ppl-box {{ border-left: 4px solid #1d4ed8; padding: .5rem .8rem; background: rgba(29,78,216,.06); border-radius: .3rem; }}
    </style>
    """
    if alto:
        css += """
        <style>
        .stApp { background: #000 !important; color: #fff !important; }
        .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div { color: #fff !important; }
        .ppl-chip { background: #000 !important; border: 2px solid #ff0 !important; color: #ff0 !important; }
        .ppl-chip .w, .ppl-chip .t { color: #ff0 !important; }
        button, .stButton button { border: 2px solid #ff0 !important; }
        a { color: #0ff !important; }
        *:focus-visible { outline: 3px solid #0ff !important; }
        </style>
        """
    else:
        css += "<style>*:focus-visible { outline: 3px solid #1d4ed8 !important; outline-offset: 2px; }</style>"
    st.markdown(css, unsafe_allow_html=True)


def painel_acessibilidade() -> None:
    st.session_state.setdefault("pref_fonte", 100)
    st.session_state.setdefault("pref_contraste", False)
    with st.sidebar.expander("Acessibilidade", expanded=False):
        st.toggle("Alto contraste", key="pref_contraste")
        st.slider("Tamanho da fonte (%)", 80, 160, step=10, key="pref_fonte")
        st.caption("As classes sempre têm rótulo textual (ex.: SUBST, ADJ), além da cor.")


def legenda() -> str:
    partes = [
        f'<span class="ppl-chip" style="--c:{CORES[c]}"><span class="w">{rotulo(c)}</span><span class="t">{SIGLAS[c]}</span></span>'
        for c in CORES
    ]
    return '<div class="ppl-legenda" aria-label="Legenda de cores das classes">' + "".join(partes) + "</div>"
