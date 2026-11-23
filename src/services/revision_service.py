"""Revisão espaçada por assunto.

Escada de intervalos: 1 → 3 → 7 → 15 → 30 dias.

* Acerto: sobe um degrau (no máximo uma vez por dia, para que vários acertos
  seguidos numa mesma sessão não empurrem o assunto para 30 dias).
* Erro: desce dois degraus e a próxima revisão passa a ser no dia seguinte.
* Ajuste por desempenho: com 4+ tentativas e taxa de acerto abaixo de 60%,
  o intervalo é reduzido pela metade (mínimo de 1 dia).
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.models import Revisao

INTERVALOS = (1, 3, 7, 15, 30)
LIMIAR_DESEMPENHO = 0.6
MIN_TENTATIVAS_AJUSTE = 4


def calcular_proximo(etapa: int, correta: bool, ja_revisado_hoje: bool) -> tuple[int, int] | None:
    """Função pura: devolve (nova_etapa, intervalo_em_dias).

    ``None`` significa "manter o agendamento atual" (acerto repetido no mesmo dia).
    """
    if correta:
        if ja_revisado_hoje:
            return None
        nova = min(etapa + 1, len(INTERVALOS) - 1)
        return nova, INTERVALOS[nova]
    return max(etapa - 2, -1), 1


def registrar_resultado(s: Session, assunto_id: str, correta: bool, hoje: date | None = None) -> Revisao:
    hoje = hoje or date.today()
    rev = s.scalar(select(Revisao).where(Revisao.assunto_id == assunto_id))
    if rev is None:
        rev = Revisao(assunto_id=assunto_id, etapa=-1, intervalo=1, proxima_data=hoje, acertos=0, erros=0, desempenho=0.0)
        s.add(rev)

    ja_hoje = rev.ultima_revisao == hoje
    proximo = calcular_proximo(rev.etapa, correta, ja_hoje)

    rev.acertos = (rev.acertos or 0) + (1 if correta else 0)
    rev.erros = (rev.erros or 0) + (0 if correta else 1)
    total = rev.acertos + rev.erros
    rev.desempenho = rev.acertos / total if total else 0.0

    if proximo is None:
        s.flush()
        return rev
    etapa, intervalo = proximo

    if correta and total >= MIN_TENTATIVAS_AJUSTE and rev.desempenho < LIMIAR_DESEMPENHO:
        intervalo = max(1, math.ceil(intervalo / 2))

    rev.etapa = etapa
    rev.intervalo = intervalo
    rev.ultima_revisao = hoje
    rev.proxima_data = hoje + timedelta(days=intervalo)
    s.flush()
    return rev


def pendentes(s: Session, hoje: date | None = None) -> list[Revisao]:
    hoje = hoje or date.today()
    return list(s.scalars(select(Revisao).where(Revisao.proxima_data <= hoje).order_by(Revisao.proxima_data)))


def todas(s: Session) -> list[Revisao]:
    return list(s.scalars(select(Revisao).order_by(Revisao.proxima_data)))
