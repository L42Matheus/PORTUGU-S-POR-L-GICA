"""Motor de análise gramatical sem IA.

O que este módulo FAZ:
* segmenta o texto em frases e palavras preservando as posições originais;
* recupera análises PRÉ-VALIDADAS (revisadas manualmente) de ``data/examples``;
* decompõe contrações conhecidas (do = de + o, à = a + a...);
* lista as classes POSSÍVEIS de palavras de classe fechada (artigos,
  preposições, conjunções, pronomes, alguns advérbios e interjeições).

O que ele NÃO faz: classificar palavras de classe aberta (substantivos,
adjetivos, verbos, advérbios em geral) em texto livre. Essa classificação
depende do contexto; sem a camada de IA, o sistema informa a limitação em
vez de inventar uma resposta.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from src.core.schemas import AnaliseFrase

DATA = Path(__file__).resolve().parents[2] / "data"

_RE_TOKEN = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*|\d+(?:[.,]\d+)*|[^\w\s]", re.UNICODE)
_RE_FRASE = re.compile(r"[^.!?…]+(?:[.!?…]+|$)", re.UNICODE)


@dataclass(frozen=True)
class Token:
    texto: str
    inicio: int
    fim: int
    tipo: str  # "palavra", "numero" ou "pontuacao"


@dataclass(frozen=True)
class Frase:
    texto: str
    inicio: int
    fim: int


def tokenizar(texto: str) -> list[Token]:
    tokens = []
    for m in _RE_TOKEN.finditer(texto):
        t = m.group(0)
        tipo = "numero" if t[0].isdigit() else ("palavra" if t[0].isalpha() else "pontuacao")
        tokens.append(Token(t, m.start(), m.end(), tipo))
    return tokens


def segmentar_frases(texto: str) -> list[Frase]:
    frases = []
    for m in _RE_FRASE.finditer(texto):
        bruto = m.group(0)
        if not bruto.strip():
            continue
        esq = len(bruto) - len(bruto.lstrip())
        dir_ = len(bruto.rstrip())
        frases.append(Frase(bruto[esq:dir_], m.start() + esq, m.start() + dir_))
    return frases


def normalizar(texto: str) -> str:
    """Forma canônica para comparação: NFC, minúsculas, espaços colapsados.

    Mantém acentos (distinguem palavras: e/é, a/à). Nunca é usada para
    exibição — o texto original é sempre preservado.
    """
    t = unicodedata.normalize("NFC", texto).casefold()
    t = re.sub(r"\s+", " ", t).strip()
    return t


# --------------------------------------------------------------------------- #
# Análises pré-validadas
# --------------------------------------------------------------------------- #


def _posicionar(analise: AnaliseFrase) -> AnaliseFrase:
    """Calcula as posições (inicio/fim) de elementos e expressões no texto."""
    texto = analise.texto
    cursor = 0
    elementos = []
    for el in analise.elementos:
        pos = _buscar_palavra(texto, el.texto, cursor)
        if pos < 0:
            raise ValueError(f"Elemento '{el.texto}' não encontrado em '{texto}'")
        elementos.append(el.model_copy(update={"inicio": pos, "fim": pos + len(el.texto)}))
        cursor = pos + len(el.texto)
    expressoes = []
    for x in analise.expressoes:
        ini = min(e.inicio for e in elementos if e.id in x.elementos)
        fim = max(e.fim for e in elementos if e.id in x.elementos)
        if texto[ini:fim] != x.texto:
            raise ValueError(f"Expressão '{x.texto}' não corresponde ao trecho '{texto[ini:fim]}'")
        expressoes.append(x.model_copy(update={"inicio": ini, "fim": fim}))
    return analise.model_copy(update={"elementos": elementos, "expressoes": expressoes})


def _buscar_palavra(texto: str, palavra: str, inicio: int) -> int:
    """Busca ``palavra`` como palavra inteira a partir de ``inicio``."""
    padrao = re.compile(r"(?<![\w-])" + re.escape(palavra) + r"(?![\w-])")
    m = padrao.search(texto, inicio)
    return m.start() if m else -1


@lru_cache(maxsize=1)
def carregar_analises() -> tuple[AnaliseFrase, ...]:
    brutos = json.loads((DATA / "examples" / "analises.json").read_text(encoding="utf-8"))
    analises = tuple(_posicionar(AnaliseFrase.model_validate(b)) for b in brutos)
    vistos = [normalizar(a.texto) for a in analises]
    if len(vistos) != len(set(vistos)):
        raise ValueError("Há frases pré-validadas duplicadas")
    return analises


def buscar_pre_validada(frase: str) -> AnaliseFrase | None:
    alvo = normalizar(frase)
    return next((a for a in carregar_analises() if normalizar(a.texto) == alvo), None)


def deslocar(analise: AnaliseFrase, base: int) -> AnaliseFrase:
    """Ajusta posições de uma análise de frase para o texto completo."""
    return analise.model_copy(
        update={
            "elementos": [e.model_copy(update={"inicio": e.inicio + base, "fim": e.fim + base}) for e in analise.elementos],
            "expressoes": [x.model_copy(update={"inicio": x.inicio + base, "fim": x.fim + base}) for x in analise.expressoes],
        }
    )


# --------------------------------------------------------------------------- #
# Pré-análise lexical (classes fechadas)
# --------------------------------------------------------------------------- #

CONTRACOES: dict[str, list[tuple[str, str]]] = {
    "à": [("a", "preposicao"), ("a", "artigo")],
    "às": [("a", "preposicao"), ("as", "artigo")],
    "ao": [("a", "preposicao"), ("o", "artigo")],
    "aos": [("a", "preposicao"), ("os", "artigo")],
    "do": [("de", "preposicao"), ("o", "artigo")],
    "da": [("de", "preposicao"), ("a", "artigo")],
    "dos": [("de", "preposicao"), ("os", "artigo")],
    "das": [("de", "preposicao"), ("as", "artigo")],
    "no": [("em", "preposicao"), ("o", "artigo")],
    "na": [("em", "preposicao"), ("a", "artigo")],
    "nos": [("em", "preposicao"), ("os", "artigo")],
    "nas": [("em", "preposicao"), ("as", "artigo")],
    "pelo": [("por", "preposicao"), ("o", "artigo")],
    "pela": [("por", "preposicao"), ("a", "artigo")],
    "pelos": [("por", "preposicao"), ("os", "artigo")],
    "pelas": [("por", "preposicao"), ("as", "artigo")],
    "num": [("em", "preposicao"), ("um", "artigo")],
    "numa": [("em", "preposicao"), ("uma", "artigo")],
    "dum": [("de", "preposicao"), ("um", "artigo")],
    "duma": [("de", "preposicao"), ("uma", "artigo")],
    "deste": [("de", "preposicao"), ("este", "pronome")],
    "desta": [("de", "preposicao"), ("esta", "pronome")],
    "desse": [("de", "preposicao"), ("esse", "pronome")],
    "dessa": [("de", "preposicao"), ("essa", "pronome")],
    "daquele": [("de", "preposicao"), ("aquele", "pronome")],
    "daquela": [("de", "preposicao"), ("aquela", "pronome")],
    "disto": [("de", "preposicao"), ("isto", "pronome")],
    "disso": [("de", "preposicao"), ("isso", "pronome")],
    "daquilo": [("de", "preposicao"), ("aquilo", "pronome")],
    "neste": [("em", "preposicao"), ("este", "pronome")],
    "nesta": [("em", "preposicao"), ("esta", "pronome")],
    "nesse": [("em", "preposicao"), ("esse", "pronome")],
    "nessa": [("em", "preposicao"), ("essa", "pronome")],
    "naquele": [("em", "preposicao"), ("aquele", "pronome")],
    "naquela": [("em", "preposicao"), ("aquela", "pronome")],
    "nisto": [("em", "preposicao"), ("isto", "pronome")],
    "nisso": [("em", "preposicao"), ("isso", "pronome")],
    "naquilo": [("em", "preposicao"), ("aquilo", "pronome")],
    "àquele": [("a", "preposicao"), ("aquele", "pronome")],
    "àquela": [("a", "preposicao"), ("aquela", "pronome")],
    "àquilo": [("a", "preposicao"), ("aquilo", "pronome")],
    "dele": [("de", "preposicao"), ("ele", "pronome")],
    "dela": [("de", "preposicao"), ("ela", "pronome")],
    "deles": [("de", "preposicao"), ("eles", "pronome")],
    "delas": [("de", "preposicao"), ("elas", "pronome")],
    "nele": [("em", "preposicao"), ("ele", "pronome")],
    "nela": [("em", "preposicao"), ("ela", "pronome")],
}

_POSSIB: dict[str, list[tuple[str, str]]] = {}


def _reg(palavras: str, classe: str, obs: str) -> None:
    for p in palavras.split():
        _POSSIB.setdefault(p, []).append((classe, obs))


_reg("o os", "artigo", "artigo definido, se determinar um substantivo seguinte")
_reg("o os", "pronome", "pronome oblíquo, se substituir um nome junto a verbo (ex.: 'eu o vi')")
_reg("a as", "artigo", "artigo definido, se determinar um substantivo seguinte")
_reg("a as", "pronome", "pronome oblíquo, se substituir um nome junto a verbo")
_reg("a", "preposicao", "preposição, se ligar termos (ex.: 'entreguei a carta a Maria')")
_reg("um uma uns umas", "artigo", "artigo indefinido, se apenas indeterminar o substantivo")
_reg("um uma", "numeral", "numeral cardinal, se o contexto destacar a quantidade")
_reg("uns umas", "pronome", "pronome indefinido em alguns usos ('uns dez alunos')")
_reg("ante após até com contra de desde em entre para perante por sem sob sobre trás", "preposicao", "preposição essencial")
_reg("até", "adverbio", "palavra denotativa de inclusão em alguns usos ('até ele veio')")
_reg("conforme segundo durante mediante exceto salvo consoante", "preposicao", "preposição acidental, se ligar termos")
_reg("conforme segundo", "conjuncao", "conjunção conformativa, se introduzir oração")
_reg("segundo", "numeral", "numeral ordinal ('segundo lugar')")
_reg("e nem", "conjuncao", "conjunção coordenativa aditiva")
_reg("mas porém contudo todavia entretanto", "conjuncao", "conjunção coordenativa adversativa (oposição)")
_reg("ou", "conjuncao", "conjunção coordenativa alternativa")
_reg("logo portanto", "conjuncao", "conjunção coordenativa conclusiva")
_reg("logo", "adverbio", "advérbio de tempo ('chego logo')")
_reg("pois", "conjuncao", "conjunção explicativa (anteposta) ou conclusiva (posposta ao verbo)")
_reg("porque", "conjuncao", "conjunção causal ou explicativa, conforme o sentido")
_reg("embora", "conjuncao", "conjunção subordinativa concessiva")
_reg("caso", "conjuncao", "conjunção condicional, se introduzir oração")
_reg("caso", "substantivo", "substantivo ('o caso')")
_reg("quando", "conjuncao", "conjunção temporal, se ligar orações")
_reg("quando", "adverbio", "advérbio interrogativo de tempo ('Quando vens?')")
_reg("que", "pronome", "pronome relativo (retoma termo anterior) ou interrogativo")
_reg("que", "conjuncao", "conjunção integrante, causal, comparativa, consecutiva...")
_reg("que", "adverbio", "advérbio de intensidade ('Que lindo!')")
_reg("se", "conjuncao", "conjunção condicional ou integrante")
_reg("se", "pronome", "pronome oblíquo/reflexivo, partícula apassivadora ou índice de indeterminação")
_reg("como", "conjuncao", "conjunção causal, conformativa ou comparativa")
_reg("como", "adverbio", "advérbio interrogativo de modo ('Como vai?')")
_reg("como", "preposicao", "preposição acidental ('atuou como juiz')")
_reg("eu tu ele ela nós vós eles elas você vocês", "pronome", "pronome pessoal do caso reto (pronome substantivo)")
_reg("me te lhe lhes vos mim ti si comigo contigo conosco convosco", "pronome", "pronome pessoal oblíquo")
_reg("nos", "pronome", "pronome pessoal oblíquo ('ele nos viu')")
_reg("meu minha meus minhas teu tua teus tuas seu sua seus suas nosso nossa nossos nossas vosso vossa", "pronome", "pronome possessivo (adjetivo se acompanha nome; substantivo se o substitui)")
_reg("este esta estes estas esse essa esses essas aquele aquela aqueles aquelas", "pronome", "pronome demonstrativo (adjetivo se acompanha nome; substantivo se o substitui)")
_reg("isto isso aquilo", "pronome", "pronome demonstrativo substantivo")
_reg("algum alguma alguns algumas nenhum nenhuma outro outra outros outras vários várias certo certa certos certas qualquer quaisquer todo toda todos todas", "pronome", "pronome indefinido")
_reg("alguém ninguém tudo nada cada", "pronome", "pronome indefinido")
_reg("muito muita muitos muitas pouco pouca poucos poucas bastante bastantes", "pronome", "pronome indefinido, se acompanhar e concordar com um nome")
_reg("muito pouco bastante", "adverbio", "advérbio de intensidade, se modificar verbo, adjetivo ou advérbio")
_reg("quem qual quais cujo cuja cujos cujas onde", "pronome", "pronome relativo ou interrogativo")
_reg("onde", "adverbio", "advérbio interrogativo de lugar")
_reg("não jamais", "adverbio", "advérbio de negação")
_reg("nunca", "adverbio", "advérbio de tempo/negação")
_reg("sim", "adverbio", "advérbio de afirmação")
_reg("talvez", "adverbio", "advérbio de dúvida")
_reg("ontem hoje amanhã cedo tarde sempre já ainda agora antes depois", "adverbio", "advérbio de tempo (mas pode ser substantivado: 'o amanhã')")
_reg("aqui ali lá cá aí longe perto", "adverbio", "advérbio de lugar")
_reg("bem mal assim devagar", "adverbio", "advérbio de modo")
_reg("tão demais", "adverbio", "advérbio de intensidade")
_reg("ah oh ufa ai ui oba opa psiu olá oi viva bravo puxa nossa ei eba", "interjeicao", "interjeição, se isolada e com valor emotivo")
_reg("nossa", "pronome", "pronome possessivo ('nossa casa')")
_reg("primeiro primeira segundo segunda terceiro terceira dobro triplo metade", "numeral", "numeral (ordinal, multiplicativo ou fracionário)")
_reg("dois duas três quatro cinco seis sete oito nove dez cem mil", "numeral", "numeral cardinal")
_reg("é", "verbo", "forma do verbo 'ser' (não confundir com a conjunção 'e')")
_reg("foi", "verbo", "forma do verbo 'ser' ou 'ir'")
_reg("está estava", "verbo", "forma do verbo 'estar'")


@dataclass
class PistaLexical:
    texto: str
    inicio: int
    fim: int
    possibilidades: list[tuple[str, str]] = field(default_factory=list)
    componentes: list[tuple[str, str]] = field(default_factory=list)
    observacao: str = ""

    @property
    def classe_fechada(self) -> bool:
        return bool(self.possibilidades or self.componentes)


def pre_analise_lexical(texto: str) -> list[PistaLexical]:
    """Pistas sobre classes POSSÍVEIS — nunca uma classificação definitiva."""
    pistas = []
    for tok in tokenizar(texto):
        if tok.tipo == "pontuacao":
            continue
        chave = normalizar(tok.texto)
        p = PistaLexical(tok.texto, tok.inicio, tok.fim)
        if tok.tipo == "numero":
            p.possibilidades = [("numeral", "algarismo: indica quantidade ou ordem")]
        elif chave in CONTRACOES:
            p.componentes = CONTRACOES[chave]
            p.observacao = "contração: " + " + ".join(f"{t} ({c})" for t, c in CONTRACOES[chave])
            if chave in {"nos"}:
                p.possibilidades = _POSSIB.get(chave, [])
        else:
            p.possibilidades = list(_POSSIB.get(chave, []))
            if not p.possibilidades:
                if chave.endswith("mente") and len(chave) > 6:
                    p.possibilidades = [("adverbio", "sufixo -mente: provável advérbio; a circunstância depende do sentido")]
                else:
                    p.observacao = "classe aberta: depende do contexto (substantivo, adjetivo, verbo...)"
        pistas.append(p)
    return pistas
