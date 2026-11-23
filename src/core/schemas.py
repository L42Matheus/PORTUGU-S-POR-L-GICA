"""Contratos de dados validados com Pydantic.

Usados para: (1) validar os arquivos didáticos em ``data/``; (2) validar a
saída da camada de IA antes de exibi-la; (3) trafegar resultados entre
serviços e interface.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Vocabulário controlado
# --------------------------------------------------------------------------- #

ClasseGramatical = Literal[
    "substantivo",
    "adjetivo",
    "artigo",
    "numeral",
    "pronome",
    "verbo",
    "adverbio",
    "preposicao",
    "conjuncao",
    "interjeicao",
]

CLASSES: tuple[str, ...] = ClasseGramatical.__args__  # type: ignore[attr-defined]

ROTULO_CLASSE: dict[str, str] = {
    "substantivo": "Substantivo",
    "adjetivo": "Adjetivo",
    "artigo": "Artigo",
    "numeral": "Numeral",
    "pronome": "Pronome",
    "verbo": "Verbo",
    "adverbio": "Advérbio",
    "preposicao": "Preposição",
    "conjuncao": "Conjunção",
    "interjeicao": "Interjeição",
    "contracao": "Contração",
}

TipoExpressao = Literal[
    "locucao_adjetiva",
    "locucao_adverbial",
    "locucao_verbal",
    "locucao_prepositiva",
    "locucao_conjuntiva",
    "expressao_adverbial",
]

ROTULO_EXPRESSAO: dict[str, str] = {
    "locucao_adjetiva": "Locução adjetiva",
    "locucao_adverbial": "Locução adverbial",
    "locucao_verbal": "Locução verbal",
    "locucao_prepositiva": "Locução prepositiva",
    "locucao_conjuntiva": "Locução conjuntiva",
    "expressao_adverbial": "Expressão de valor adverbial",
}

Confianca = Literal["alta", "media", "baixa"]
Dificuldade = Literal["iniciante", "intermediario", "avancado"]
AreaId = Literal["nomes", "verbos", "conectivos", "complementares"]

TipoQuestao = Literal[
    "multipla_escolha",
    "verdadeiro_falso",
    "associacao",
    "identificar_palavra",
    "identificar_classe",
    "completar",
    "identificar_relacao",
    "encontrar_erro",
    "comparar",
    "justificativa",
]

TIPOS_COM_ALTERNATIVAS = {
    "multipla_escolha",
    "verdadeiro_falso",
    "identificar_palavra",
    "identificar_classe",
    "completar",
    "identificar_relacao",
    "encontrar_erro",
    "comparar",
}


class Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Áreas e lições
# --------------------------------------------------------------------------- #


class AssuntoSchema(Estrito):
    id: str
    nome: str
    nivel: Dificuldade = "iniciante"


class AreaSchema(Estrito):
    id: AreaId
    nome: str
    descricao: str
    conceito_central: str
    ordem: int
    assuntos: list[AssuntoSchema]


class Exemplo(Estrito):
    frase: str
    destaque: str | None = None
    explicacao: str


class Comparacao(Estrito):
    frase: str
    palavra: str
    classificacao: str
    explicacao: str


class Subtopico(Estrito):
    titulo: str
    texto: str
    exemplos: list[str] = Field(default_factory=list)


class Logica(Estrito):
    pseudocodigo: str
    python: str
    fluxograma: str  # linguagem DOT (Graphviz)
    limitacoes: list[str]


class Licao(Estrito):
    id: str
    area: AreaId
    assunto: str
    titulo: str
    nivel: Dificuldade
    classe_ou_expressao: str
    conceito: str
    subtopicos: list[Subtopico]
    regras: list[str]
    exemplos: list[Exemplo]
    contraexemplos: list[Exemplo]
    excecoes: list[str]
    comparacoes: list[Comparacao]
    logica: Logica

    @field_validator("exemplos", "regras")
    @classmethod
    def _nao_vazio(cls, v):
        if not v:
            raise ValueError("lista obrigatória não pode ser vazia")
        return v


# --------------------------------------------------------------------------- #
# Questões
# --------------------------------------------------------------------------- #


class Alternativa(Estrito):
    letra: str
    texto: str
    comentario: str | None = None


class Par(Estrito):
    item: str
    resposta: str


class QuestaoSchema(Estrito):
    id: str
    area: AreaId
    assunto: str
    dificuldade: Dificuldade
    tipo: TipoQuestao
    texto_base: str | None = None
    destaque: str | None = None
    enunciado: str
    alternativas: list[Alternativa] = Field(default_factory=list)
    pares: list[Par] = Field(default_factory=list)
    resposta: str
    justificativa: str
    regra: str
    exemplos_relacionados: list[str] = Field(default_factory=list)
    palavras_chave: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coerencia(self):
        if self.tipo in TIPOS_COM_ALTERNATIVAS:
            if len(self.alternativas) < 2:
                raise ValueError(f"{self.id}: questão '{self.tipo}' exige alternativas")
            letras = [a.letra for a in self.alternativas]
            if len(set(letras)) != len(letras):
                raise ValueError(f"{self.id}: letras repetidas")
            if self.resposta not in letras:
                raise ValueError(f"{self.id}: resposta '{self.resposta}' não está nas alternativas")
        if self.tipo == "verdadeiro_falso":
            if {a.letra for a in self.alternativas} != {"V", "F"}:
                raise ValueError(f"{self.id}: V/F exige alternativas V e F")
        if self.tipo == "associacao":
            if len(self.pares) < 2:
                raise ValueError(f"{self.id}: associação exige ao menos dois pares")
        if self.tipo == "justificativa" and not self.palavras_chave:
            raise ValueError(f"{self.id}: justificativa exige palavras-chave de referência")
        if self.destaque and self.texto_base and self.destaque not in self.texto_base:
            raise ValueError(f"{self.id}: destaque '{self.destaque}' ausente do texto-base")
        return self

    @property
    def letras(self) -> list[str]:
        return [a.letra for a in self.alternativas]

    def alternativa(self, letra: str) -> Alternativa | None:
        return next((a for a in self.alternativas if a.letra == letra), None)


# --------------------------------------------------------------------------- #
# Análise de frases
# --------------------------------------------------------------------------- #


class Componente(Estrito):
    texto: str
    classe: ClasseGramatical
    subtipo: str | None = None


class ClassificacaoAlternativa(Estrito):
    classe: ClasseGramatical
    condicao: str


class Elemento(Estrito):
    id: str
    texto: str
    inicio: int = -1
    fim: int = -1
    classe: ClasseGramatical | Literal["contracao"]
    subtipo: str | None = None
    componentes: list[Componente] = Field(default_factory=list)
    relacionado_a: str | None = None  # id de outro elemento
    relacao: str | None = None
    funcao_sintatica: str | None = None
    justificativa: str
    confianca: Confianca = "alta"
    classificacoes_alternativas: list[ClassificacaoAlternativa] = Field(default_factory=list)

    @model_validator(mode="after")
    def _contracao(self):
        if self.classe == "contracao" and len(self.componentes) < 2:
            raise ValueError(f"contração '{self.texto}' precisa de ao menos dois componentes")
        return self


class Expressao(Estrito):
    id: str
    texto: str
    inicio: int = -1
    fim: int = -1
    tipo: TipoExpressao
    subtipo: str | None = None
    elementos: list[str]
    relacionado_a: str | None = None
    justificativa: str


class FraseComparada(Estrito):
    frase: str
    explicacao: str


class AnaliseFrase(Estrito):
    texto: str
    area_principal: AreaId
    assunto_principal: str
    explicacao: str
    elementos: list[Elemento]
    expressoes: list[Expressao] = Field(default_factory=list)
    nivel_sintatico: list[str] = Field(default_factory=list)
    ambiguidades: list[str] = Field(default_factory=list)
    comparacoes: list[FraseComparada] = Field(default_factory=list)
    origem: Literal["pre_validada", "ia"] = "pre_validada"
    avisos: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _referencias(self):
        ids = {e.id for e in self.elementos}
        if len(ids) != len(self.elementos):
            raise ValueError("ids de elementos repetidos")
        for e in self.elementos:
            if e.relacionado_a and e.relacionado_a not in ids:
                raise ValueError(f"'{e.texto}' relacionado a id inexistente {e.relacionado_a}")
        for x in self.expressoes:
            faltando = [i for i in x.elementos if i not in ids]
            if faltando:
                raise ValueError(f"expressão '{x.texto}' referencia ids inexistentes {faltando}")
            if x.relacionado_a and x.relacionado_a not in ids:
                raise ValueError(f"expressão '{x.texto}' relacionada a id inexistente")
        return self

    def elemento(self, id_: str | None) -> Elemento | None:
        return next((e for e in self.elementos if e.id == id_), None)


# --------------------------------------------------------------------------- #
# Tutor socrático (roteiros pré-validados)
# --------------------------------------------------------------------------- #


class OpcaoTutor(Estrito):
    texto: str
    correta: bool
    retorno: str


class PassoTutor(Estrito):
    pergunta: str
    opcoes: list[OpcaoTutor]

    @model_validator(mode="after")
    def _uma_correta(self):
        if sum(o.correta for o in self.opcoes) != 1:
            raise ValueError("cada passo do tutor precisa de exatamente uma opção correta")
        return self


class RoteiroTutor(Estrito):
    id: str
    assunto: str
    frase: str
    alvo: str
    pergunta_inicial: str
    classe_correta: ClasseGramatical
    # Quando o alvo é uma expressão (locução), as opções iniciais são explícitas
    # e a primeira é a correta; caso contrário, usam-se as dez classes.
    opcoes_iniciais: list[str] = Field(default_factory=list)
    justificativas: list[OpcaoTutor]
    passos: list[PassoTutor]
    conclusao: str
    contraexemplo: str

    @model_validator(mode="after")
    def _alvo(self):
        if self.alvo not in self.frase:
            raise ValueError(f"alvo '{self.alvo}' não aparece na frase")
        if sum(o.correta for o in self.justificativas) != 1:
            raise ValueError("as justificativas precisam ter exatamente uma correta")
        return self


# --------------------------------------------------------------------------- #
# Saídas da IA
# --------------------------------------------------------------------------- #


class AnaliseAlternativaIA(Estrito):
    letra: str
    avaliacao: Literal["correta", "incorreta", "indeterminada"]
    explicacao: str


class ResolucaoIA(Estrito):
    assunto: str
    comando_interpretado: str
    elementos_relevantes: list[str]
    raciocinio: list[str]
    alternativas: list[AnaliseAlternativaIA]
    gabarito_sugerido: str | None
    justificativa_gabarito: str
    incertezas: list[str]
    questao_fixacao: str
    avisos: list[str] = Field(default_factory=list)


class AvaliacaoJustificativaIA(Estrito):
    veredito: Literal["adequada", "parcial", "inadequada"]
    pontos_corretos: list[str]
    problemas: list[str]
    comentario: str
