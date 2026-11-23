from collections import Counter

import pytest

from src.core.schemas import QuestaoSchema
from src.services import content_service as c
from src.services import feedback_service, question_parser, question_service


def test_banco_tem_ao_menos_60_questoes_distribuidas():
    qs = c.carregar_questoes()
    assert len(qs) >= 60
    por_area = Counter(q.area for q in qs)
    for area in ("nomes", "verbos", "conectivos"):
        assert por_area[area] >= 15, area


def test_tipos_de_exercicio_exigidos_estao_presentes():
    tipos = {q.tipo for q in c.carregar_questoes()}
    exigidos = {
        "multipla_escolha", "verdadeiro_falso", "associacao", "identificar_palavra", "identificar_classe",
        "completar", "identificar_relacao", "encontrar_erro", "comparar", "justificativa",
    }
    assert exigidos <= tipos


def test_campos_obrigatorios_preenchidos():
    for q in c.carregar_questoes():
        assert q.enunciado and q.justificativa and q.regra and q.tags, q.id


def test_frases_nao_se_repetem_em_excesso():
    textos = Counter(q.texto_base for q in c.carregar_questoes() if q.texto_base)
    assert max(textos.values()) <= 3


def test_validacao_rejeita_resposta_fora_das_alternativas():
    with pytest.raises(ValueError):
        QuestaoSchema.model_validate(
            {
                "id": "X", "area": "nomes", "assunto": "adjetivo", "dificuldade": "iniciante", "tipo": "multipla_escolha",
                "enunciado": "?", "alternativas": [{"letra": "A", "texto": "a"}, {"letra": "B", "texto": "b"}],
                "resposta": "C", "justificativa": "j", "regra": "r",
            }
        )


def test_validacao_rejeita_destaque_ausente():
    with pytest.raises(ValueError):
        QuestaoSchema.model_validate(
            {
                "id": "X", "area": "nomes", "assunto": "adjetivo", "dificuldade": "iniciante", "tipo": "multipla_escolha",
                "texto_base": "A casa.", "destaque": "rua",
                "enunciado": "?", "alternativas": [{"letra": "A", "texto": "a"}, {"letra": "B", "texto": "b"}],
                "resposta": "A", "justificativa": "j", "regra": "r",
            }
        )


def test_correcao_multipla_escolha():
    q = c.questao_por_id("N01")
    assert question_service.corrigir(q, "A").correta is True
    assert question_service.corrigir(q, "B").correta is False
    with pytest.raises(ValueError):
        question_service.corrigir(q, "Z")


def test_correcao_associacao():
    q = c.questao_por_id("N06")
    certo = {p.item: p.resposta for p in q.pares}
    assert question_service.corrigir(q, certo).correta is True
    errado = dict(certo, cardume="lobos")
    r = question_service.corrigir(q, errado)
    assert r.correta is False and r.detalhes["por_item"]["cardume"] is False


def test_correcao_justificativa_fica_pendente_de_avaliacao():
    q = c.questao_por_id("N24")
    r = question_service.corrigir(q, "Jovem caracteriza o substantivo estudante.")
    assert r.correta is None
    assert set(r.detalhes["palavras_chave_presentes"]) == {"caracteriza", "estudante", "substantivo"}
    with pytest.raises(ValueError):
        question_service.corrigir(q, "   ")


def test_feedback_erro_traz_diagnostico_e_regra():
    q = c.questao_por_id("V17")
    fb = feedback_service.gerar(q, question_service.corrigir(q, "C"))
    assert fb.correta is False
    assert "locução adverbial" in fb.diagnostico
    assert fb.resposta_correta.startswith("B)")
    assert fb.regra


def test_feedback_acerto():
    q = c.questao_por_id("V17")
    fb = feedback_service.gerar(q, question_service.corrigir(q, "B"))
    assert fb.correta is True and fb.explicacao and fb.regra


def test_questao_semelhante_e_do_mesmo_assunto():
    q = c.questao_por_id("N01")
    sim = question_service.semelhante(q)
    assert sim is not None and sim.id != q.id and sim.assunto == q.assunto


def test_filtros_por_modo():
    for modo, tipos in question_service.MODOS_TIPOS.items():
        assert question_service.filtrar(tipos=tipos), modo


def test_simulado_sem_justificativas():
    qs = question_service.montar_simulado(20)
    assert len(qs) == 20 and all(q.tipo != "justificativa" for q in qs)


# --------------------------- interpretação de questões ----------------------


def test_parser_alternativas_e_comando_incorreta():
    texto = "Assinale a alternativa INCORRETA sobre adjetivos.\nA) um\nB) dois\nC) três\nD) quatro\nE) cinco"
    p = question_parser.interpretar(texto)
    assert p.letras == ["A", "B", "C", "D", "E"]
    assert p.comando == "incorreta"
    assert ("adjetivo", "adjetiv") in p.assuntos_detectados
    assert p.texto_original == texto


def test_parser_alternativas_inline_e_correta():
    p = question_parser.interpretar("Assinale a correta: a) x b) y c) z d) w")
    assert p.letras == ["A", "B", "C", "D"]
    assert p.comando == "correta"


def test_parser_julgamento_sem_alternativas():
    p = question_parser.interpretar("Julgue o item: em 'chegou cedo', 'cedo' é advérbio de tempo.")
    assert p.comando == "julgamento" and p.alternativas == []


def test_parser_entrada_vazia():
    with pytest.raises(ValueError):
        question_parser.interpretar("   ")


def test_parser_nao_inventa_alternativas():
    p = question_parser.interpretar("Qual a classe de 'cedo' em 'João chegou cedo'?")
    assert p.alternativas == []
    assert p.avisos


def test_busca_no_banco_encontra_questao_colada():
    q = c.questao_por_id("C17")
    texto = q.enunciado + "\n" + "\n".join(f"{a.letra}) {a.texto}" for a in q.alternativas)
    achada = question_parser.buscar_no_banco(question_parser.interpretar(texto))
    assert achada is not None and achada.id == "C17"


def test_busca_no_banco_nao_associa_questao_alheia():
    p = question_parser.interpretar("Assinale a alternativa sobre ortografia.\nA) casa\nB) kasa\nC) caza\nD) cassa")
    assert question_parser.buscar_no_banco(p) is None


def test_licoes_e_roteiros_carregam():
    assert len(c.carregar_licoes()) >= 12
    classes = {lic.assunto for lic in c.carregar_licoes()}
    for a in ("substantivo", "adjetivo", "artigo", "pronome", "numeral", "verbo", "adverbio", "preposicao", "conjuncao", "interjeicao"):
        assert a in classes
    assert c.carregar_roteiros()
