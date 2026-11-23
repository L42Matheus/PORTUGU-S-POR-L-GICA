from datetime import date, timedelta

from src.services import revision_service as r

HOJE = date(2026, 1, 10)


def test_escada_de_intervalos_com_acertos_em_dias_diferentes(s):
    esperado = [1, 3, 7, 15, 30, 30]
    dia = HOJE
    for intervalo in esperado:
        rev = r.registrar_resultado(s, "adjetivo", True, dia)
        assert rev.intervalo == intervalo
        assert rev.proxima_data == dia + timedelta(days=intervalo)
        dia = rev.proxima_data


def test_erro_reduz_intervalo_e_volta_amanha(s):
    dia = HOJE
    for _ in range(4):
        rev = r.registrar_resultado(s, "verbo", True, dia)
        dia = rev.proxima_data
    assert rev.intervalo == 15
    rev = r.registrar_resultado(s, "verbo", False, dia)
    assert rev.intervalo == 1
    assert rev.proxima_data == dia + timedelta(days=1)
    assert rev.etapa == 1  # desceu dois degraus (3 -> 1)


def test_varios_acertos_no_mesmo_dia_nao_avancam(s):
    r.registrar_resultado(s, "artigo", True, HOJE)
    rev = r.registrar_resultado(s, "artigo", True, HOJE)
    rev = r.registrar_resultado(s, "artigo", True, HOJE)
    assert rev.intervalo == 1 and rev.acertos == 3


def test_acerto_depois_de_erro_no_mesmo_dia_mantem_revisao_amanha(s):
    r.registrar_resultado(s, "pronome", True, HOJE - timedelta(days=5))
    r.registrar_resultado(s, "pronome", False, HOJE)
    rev = r.registrar_resultado(s, "pronome", True, HOJE)
    assert rev.proxima_data == HOJE + timedelta(days=1)


def test_desempenho_baixo_encurta_intervalo(s):
    dia = HOJE
    for correta in (False, False, False):
        r.registrar_resultado(s, "numeral", correta, dia)
        dia += timedelta(days=1)
    rev = r.registrar_resultado(s, "numeral", True, dia)
    assert rev.desempenho == 0.25
    assert rev.intervalo == 1  # 1 dia (mínimo), já reduzido


def test_pendentes(s):
    r.registrar_resultado(s, "substantivo", True, HOJE)  # próxima: HOJE+1
    r.registrar_resultado(s, "conjuncao", False, HOJE - timedelta(days=3))  # próxima: HOJE-2
    ids = [x.assunto_id for x in r.pendentes(s, HOJE)]
    assert ids == ["conjuncao"]
    assert {x.assunto_id for x in r.pendentes(s, HOJE + timedelta(days=1))} == {"conjuncao", "substantivo"}


def test_funcao_pura():
    assert r.calcular_proximo(-1, True, False) == (0, 1)
    assert r.calcular_proximo(4, True, False) == (4, 30)
    assert r.calcular_proximo(0, False, False) == (-1, 1)
    assert r.calcular_proximo(2, True, True) is None
