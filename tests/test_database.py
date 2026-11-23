from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core import models
from src.core.database import MIGRACOES, criar_engine, migrar, sessao
from src.services import question_service, stats_service
from src.services.content_service import carregar_questoes, questao_por_id, sincronizar_conteudo


def test_migracoes_sao_idempotentes(tmp_path):
    eng = criar_engine(f"sqlite:///{tmp_path / 'm.db'}")
    assert migrar(eng) == MIGRACOES[-1][0]
    assert migrar(eng) == MIGRACOES[-1][0]


def test_conteudo_sincronizado(s):
    assert s.query(models.Questao).count() == len(carregar_questoes())
    assert s.query(models.AreaEstudo).count() == 4
    sincronizar_conteudo(s)  # segunda vez não duplica
    assert s.query(models.Questao).count() == len(carregar_questoes())


def test_persistencia_das_respostas(fabrica):
    q = questao_por_id("N02")
    with sessao(fabrica) as s:
        question_service.registrar_tentativa(s, q, "B", True, 12.5, "treino")
    with sessao(fabrica) as s:
        t = s.scalar(select(models.Tentativa))
        assert (t.questao_id, t.resposta_usuario, t.correta, t.tempo_resposta) == ("N02", "B", True, 12.5)
        assert s.scalar(select(models.Revisao).where(models.Revisao.assunto_id == "adjetivo")) is not None


def test_integridade_referencial(s):
    s.add(models.Tentativa(questao_id="NAO_EXISTE", resposta_usuario="A", correta=True))
    with pytest.raises(IntegrityError):
        s.flush()
    s.rollback()


def test_restricao_de_dificuldade(s):
    s.add(models.Questao(id="ZZ", assunto_id="adjetivo", tipo="multipla_escolha", enunciado="?", resposta="A", justificativa="j", dificuldade="facil"))
    with pytest.raises(IntegrityError):
        s.flush()
    s.rollback()


def test_calculo_de_acertos(s):
    base = datetime(2026, 1, 5, 10)
    respostas = [("N01", "A", True), ("N02", "A", False), ("V09", "B", True), ("C01", "A", True)]
    for i, (qid, resp, ok) in enumerate(respostas):
        question_service.registrar_tentativa(s, questao_por_id(qid), resp, ok, 10, quando=base + timedelta(days=i))
    df = stats_service.tentativas_df(s)
    r = stats_service.resumo(df)
    assert (r.resolvidas, r.acertos, r.taxa) == (4, 3, 0.75)
    pa = stats_service.por_area(df).set_index("area")
    assert pa.loc["nomes", "taxa"] == 0.5 and pa.loc["verbos", "taxa"] == 1.0
    assert stats_service.resumo(stats_service.filtrar(df, area="nomes")).resolvidas == 2
    assert stats_service.sequencia(df, hoje=date(2026, 1, 8)) == 4


def test_justificativa_pendente_e_autoavaliacao(s):
    q = questao_por_id("N24")
    t = question_service.registrar_tentativa(s, q, "texto", None)
    assert question_service.tentativas_pendentes_avaliacao(s)
    assert stats_service.resumo(stats_service.tentativas_df(s)).taxa is None
    question_service.avaliar_tentativa(s, t.id, True)
    assert not question_service.tentativas_pendentes_avaliacao(s)


def test_erros_pendentes_somem_apos_acerto(s):
    q = questao_por_id("V01")
    question_service.registrar_tentativa(s, q, "B", False)
    assert [x.id for x, _ in question_service.questoes_com_erro_pendente(s)] == ["V01"]
    question_service.registrar_tentativa(s, q, "A", True)
    assert question_service.questoes_com_erro_pendente(s) == []


def test_simulado_registrado(s):
    qs = question_service.montar_simulado(3)
    sim = question_service.iniciar_simulado(s, 3, None, None)
    for q, ok in zip(qs, (True, False, True)):
        question_service.registrar_tentativa(s, q, q.resposta if ok else "?", ok, modo="simulado", simulado_id=sim.id)
    sim = question_service.concluir_simulado(s, sim.id)
    assert (sim.total, sim.acertos) == (3, 2)
    assert len(stats_service.historico_simulados(s)) == 1


def test_sequencia_de_dias():
    hoje = date(2026, 3, 10)
    assert stats_service.sequencia_dias([], hoje) == 0
    assert stats_service.sequencia_dias([hoje, hoje - timedelta(1), hoje - timedelta(2)], hoje) == 3
    assert stats_service.sequencia_dias([hoje - timedelta(1)], hoje) == 1
    assert stats_service.sequencia_dias([hoje - timedelta(3)], hoje) == 0
