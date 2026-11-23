import pytest

from src.services import grammar_service as g

# Casos gramaticais obrigatórios: palavra/expressão -> classe esperada (revisada).
CASOS = {
    "O jovem chegou.": {"O": "artigo", "jovem": "substantivo", "chegou": "verbo"},
    "O professor jovem chegou.": {"O": "artigo", "professor": "substantivo", "jovem": "adjetivo", "chegou": "verbo"},
    "O bom sempre vence.": {"O": "artigo", "bom": "substantivo", "sempre": "adverbio", "vence": "verbo"},
    "O amor é essencial.": {"amor": "substantivo", "é": "verbo", "essencial": "adjetivo"},
    "João chegou cedo.": {"João": "substantivo", "chegou": "verbo", "cedo": "adverbio"},
    "João chegou de madrugada.": {"chegou": "verbo", "de": "preposicao", "madrugada": "substantivo"},
    "Ele respondeu rapidamente.": {"Ele": "pronome", "respondeu": "verbo", "rapidamente": "adverbio"},
    "Ele estava muito feliz.": {"estava": "verbo", "muito": "adverbio", "feliz": "adjetivo"},
    "Gosto de música.": {"Gosto": "verbo", "de": "preposicao", "música": "substantivo"},
    "Estudei porque precisava aprender.": {"Estudei": "verbo", "porque": "conjuncao", "aprender": "verbo"},
    "As duas meninas chegaram.": {"As": "artigo", "duas": "numeral", "meninas": "substantivo", "chegaram": "verbo"},
    "A casa de madeira foi vendida.": {"casa": "substantivo", "de": "preposicao", "madeira": "substantivo", "foi": "verbo", "vendida": "verbo"},
}

EXPRESSOES = {
    "João chegou de madrugada.": ("de madrugada", "locucao_adverbial", "tempo"),
    "A casa de madeira foi vendida.": ("de madeira", "locucao_adjetiva", None),
}


@pytest.mark.parametrize("frase,esperado", CASOS.items())
def test_casos_obrigatorios(frase, esperado):
    a = g.buscar_pre_validada(frase)
    assert a is not None, f"sem análise revisada para {frase!r}"
    obtido = {e.texto: e.classe for e in a.elementos}
    for palavra, classe in esperado.items():
        assert obtido[palavra] == classe, f"{frase}: '{palavra}'"
    assert a.explicacao.strip(), "cada caso precisa de explicação contextual"


def test_jovem_muda_de_classe_com_o_contexto():
    a1 = g.buscar_pre_validada("O jovem chegou.")
    a2 = g.buscar_pre_validada("O professor jovem chegou.")
    j2 = next(e for e in a2.elementos if e.texto == "jovem")
    assert next(e for e in a1.elementos if e.texto == "jovem").classe == "substantivo"
    assert j2.classe == "adjetivo"
    assert a2.elemento(j2.relacionado_a).texto == "professor"


def test_advérbios_se_relacionam_ao_termo_modificado():
    a = g.buscar_pre_validada("Ele estava muito feliz.")
    muito = next(e for e in a.elementos if e.texto == "muito")
    assert a.elemento(muito.relacionado_a).texto == "feliz"
    cedo = next(e for e in g.buscar_pre_validada("João chegou cedo.").elementos if e.texto == "cedo")
    assert cedo.subtipo == "tempo"


@pytest.mark.parametrize("frase,info", EXPRESSOES.items())
def test_locucoes_sao_expressoes_e_nao_classes(frase, info):
    texto, tipo, subtipo = info
    a = g.buscar_pre_validada(frase)
    x = next(x for x in a.expressoes if x.texto == texto)
    assert x.tipo == tipo
    if subtipo:
        assert x.subtipo == subtipo
    # cada palavra interna mantém sua própria classe
    assert all(a.elemento(i).classe in {"preposicao", "substantivo"} for i in x.elementos)


def test_contracao_crase_tem_dois_componentes():
    a = g.buscar_pre_validada("A menina inteligente respondeu rapidamente à questão.")
    crase = next(e for e in a.elementos if e.texto == "à")
    assert crase.classe == "contracao"
    assert [c.classe for c in crase.componentes] == ["preposicao", "artigo"]


def test_ambiguidade_declarada_quando_ha_divergencia():
    a = g.buscar_pre_validada("Estudei porque precisava aprender.")
    assert a.ambiguidades
    porque = next(e for e in a.elementos if e.texto == "porque")
    assert porque.confianca != "alta"


def test_todas_analises_tem_posicoes_coerentes():
    for a in g.carregar_analises():
        for e in a.elementos:
            assert a.texto[e.inicio : e.fim] == e.texto
        for x in a.expressoes:
            assert a.texto[x.inicio : x.fim] == x.texto


def test_busca_tolera_espacos_e_maiusculas_mas_preserva_texto():
    a = g.buscar_pre_validada("  o JOVEM   chegou. ")
    assert a is not None
    assert a.texto == "O jovem chegou."


def test_tokenizacao_preserva_posicoes():
    texto = "Ufa! O guarda-chuva custou 10,50 reais."
    for t in g.tokenizar(texto):
        assert texto[t.inicio : t.fim] == t.texto
    assert "guarda-chuva" in [t.texto for t in g.tokenizar(texto)]


def test_segmentacao_de_frases():
    texto = "João chegou cedo. Gosto de música! E você?"
    frases = g.segmentar_frases(texto)
    assert [f.texto for f in frases] == ["João chegou cedo.", "Gosto de música!", "E você?"]
    for f in frases:
        assert texto[f.inicio : f.fim] == f.texto


def test_entrada_vazia():
    assert g.segmentar_frases("") == []
    assert g.segmentar_frases("   \n ") == []
    assert g.pre_analise_lexical("") == []


def test_pre_analise_lexical_nao_classifica_classe_aberta():
    pistas = {p.texto: p for p in g.pre_analise_lexical("O cachorro latiu no quintal rapidamente.")}
    assert not pistas["cachorro"].possibilidades
    assert "classe aberta" in pistas["cachorro"].observacao
    # 'O' tem mais de uma possibilidade: artigo e pronome
    assert {c for c, _ in pistas["O"].possibilidades} == {"artigo", "pronome"}
    assert [c for _, c in pistas["no"].componentes] == ["preposicao", "artigo"]
    assert pistas["rapidamente"].possibilidades[0][0] == "adverbio"


def test_deslocar_ajusta_posicoes():
    texto = "Olá. João chegou cedo."
    fr = g.segmentar_frases(texto)[1]
    a = g.deslocar(g.buscar_pre_validada(fr.texto), fr.inicio)
    for e in a.elementos:
        assert texto[e.inicio : e.fim] == e.texto
