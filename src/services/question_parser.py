"""Interpretação determinística de questões coladas pelo estudante.

Etapas que NÃO dependem de IA: separar enunciado e alternativas, interpretar
o comando ("assinale a correta/incorreta"...), detectar palavras-chave de
assunto e procurar a questão no banco revisado.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from src.core.schemas import QuestaoSchema
from src.services.content_service import carregar_questoes, nome_assunto
from src.services.grammar_service import normalizar

_RE_ALT_LINHA = re.compile(r"^[ \t]*\(?([A-Ea-e])[\)\.\-–—][ \t]+(.+?)[ \t]*$", re.MULTILINE)
_RE_ALT_INLINE = re.compile(r"(?:^|\s)\(?([A-Ea-e])\)\s+")

COMANDOS = [
    ("incorreta", r"\bincorret|\berrad|\bexceto\b|\bsalvo\b|não (?:está|estão|é|são) corret|\bfals[ao]\b(?!.*verdadeir)", "A questão pede a alternativa INCORRETA (ou a exceção). As demais estarão corretas."),
    ("equivalencia", r"mesmo sentido|equival|sem prejuízo|mant[eé]m o sentido|preserva(?:m|ndo)? o sentido|reescrita", "A questão pede uma reescrita ou substituição que preserve o sentido (equivalência)."),
    ("diferente", r"\bdiferente|\bdistint|\bdifere\b|\bdestoa", "A questão pede o elemento que se DIFERENCIA dos demais."),
    ("julgamento", r"\bjulgue\b|certo ou errado|\(\s*c\s*\)|\bc\s*/\s*e\b", "A questão pede que você JULGUE a afirmação como certa ou errada."),
    ("correta", r"\bcorret|\bcert[ao]\b|\bverdadeir|\badequad|\bassinale\b", "A questão pede a alternativa CORRETA."),
]

PALAVRAS_ASSUNTO = [
    ("locução adjetiva", "locucao_adjetiva"),
    ("locução adverbial", "locucao_adverbial"),
    ("substantiv", "substantivo"),
    ("adjetiv", "adjetivo"),
    ("artigo", "artigo"),
    ("pronome", "pronome"),
    ("numeral", "numeral"),
    ("advérbio", "adverbio"),
    ("adverbia", "adverbio"),
    ("verbo", "verbo"),
    ("verbal", "verbo"),
    ("preposiç", "preposicao"),
    ("crase", "preposicao"),
    ("conjunç", "conjuncao"),
    ("conectivo", "conjuncao"),
    ("interjeiç", "interjeicao"),
]


@dataclass
class AlternativaParseada:
    letra: str
    texto: str


@dataclass
class QuestaoParseada:
    texto_original: str
    enunciado: str
    alternativas: list[AlternativaParseada]
    comando: str
    comando_explicacao: str
    assuntos_detectados: list[tuple[str, str]]
    avisos: list[str] = field(default_factory=list)

    @property
    def letras(self) -> list[str]:
        return [a.letra for a in self.alternativas]


def _extrair_alternativas(texto: str) -> tuple[str, list[AlternativaParseada]]:
    linhas = list(_RE_ALT_LINHA.finditer(texto))
    letras = [m.group(1).upper() for m in linhas]
    esperado = [chr(ord("A") + i) for i in range(len(letras))]
    if len(linhas) >= 2 and letras == esperado:
        return texto[: linhas[0].start()].strip(), [AlternativaParseada(m.group(1).upper(), m.group(2).strip()) for m in linhas]

    inline = list(_RE_ALT_INLINE.finditer(texto))
    letras = [m.group(1).upper() for m in inline]
    esperado = [chr(ord("A") + i) for i in range(len(letras))]
    if len(inline) >= 2 and letras == esperado:
        alts = []
        for i, m in enumerate(inline):
            fim = inline[i + 1].start() if i + 1 < len(inline) else len(texto)
            alts.append(AlternativaParseada(m.group(1).upper(), texto[m.end() : fim].strip()))
        return texto[: inline[0].start()].strip(), alts
    return texto.strip(), []


def interpretar(texto: str) -> QuestaoParseada:
    if not texto or not texto.strip():
        raise ValueError("Cole o enunciado da questão antes de analisar.")
    enunciado, alternativas = _extrair_alternativas(texto)
    norm = normalizar(enunciado)

    comando, explicacao = "indefinido", "Não identifiquei um comando explícito (ex.: 'assinale a correta'). Leia o enunciado com atenção para saber o que é pedido."
    for nome, padrao, expl in COMANDOS:
        if re.search(padrao, norm):
            comando, explicacao = nome, expl
            break
    if comando == "correta" and not alternativas and re.search(r"\bjulgue\b", norm):
        comando = "julgamento"

    vistos: dict[str, str] = {}
    for termo, assunto in PALAVRAS_ASSUNTO:
        if termo in norm and assunto not in vistos:
            vistos[assunto] = termo
    assuntos = [(a, t) for a, t in vistos.items()]
    # "locução adjetiva" não deve contar também como "adjetivo" genérico.
    if "locucao_adjetiva" in vistos:
        assuntos = [x for x in assuntos if not (x[0] == "adjetivo" and x[1] == "adjetiv")]
    if "locucao_adverbial" in vistos:
        assuntos = [x for x in assuntos if not (x[0] == "adverbio" and x[1] == "adverbia")]

    avisos = []
    if not alternativas and comando != "julgamento":
        avisos.append("Não encontrei alternativas no formato 'A) ...'. Se a questão tiver alternativas, coloque cada uma em uma linha.")
    elif alternativas and len(alternativas) < 4:
        avisos.append(f"Encontrei apenas {len(alternativas)} alternativas. Confira se alguma ficou de fora.")
    return QuestaoParseada(texto, enunciado, alternativas, comando, explicacao, assuntos, avisos)


def descrever_assuntos(p: QuestaoParseada) -> str:
    if not p.assuntos_detectados:
        return "Nenhuma palavra-chave de assunto gramatical foi encontrada no enunciado."
    nomes = ", ".join(f"{nome_assunto(a)} (termo '{t}')" for a, t in p.assuntos_detectados)
    return f"Palavras-chave encontradas no enunciado: {nomes}. Isso é uma detecção por termos, não uma análise do conteúdo."


def buscar_no_banco(p: QuestaoParseada, limiar: float = 0.82) -> QuestaoSchema | None:
    """Procura uma questão revisada equivalente à colada (para resolução comentada)."""
    alvo = normalizar(p.enunciado)
    alts_alvo = {normalizar(a.texto) for a in p.alternativas}
    melhor, nota_melhor = None, 0.0
    for q in carregar_questoes():
        base = normalizar(" ".join(x for x in [q.texto_base or "", q.enunciado] if x))
        nota = max(
            difflib.SequenceMatcher(None, alvo, base).ratio(),
            difflib.SequenceMatcher(None, alvo, normalizar(q.enunciado)).ratio(),
        )
        if alts_alvo and q.alternativas:
            alts_q = {normalizar(a.texto) for a in q.alternativas}
            nota = 0.5 * nota + 0.5 * (len(alts_alvo & alts_q) / max(len(alts_q), 1))
        if nota > nota_melhor:
            melhor, nota_melhor = q, nota
    return melhor if nota_melhor >= limiar else None
