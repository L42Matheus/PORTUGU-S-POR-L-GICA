"""Banco de questões: seleção, correção e registro de tentativas."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.models import Simulado, Tentativa
from src.core.schemas import QuestaoSchema
from src.services import revision_service
from src.services.content_service import carregar_questoes, questao_por_id
from src.services.grammar_service import normalizar

MODOS_TIPOS: dict[str, set[str]] = {
    "identificar": {"identificar_classe", "identificar_palavra"},
    "relacionar": {"associacao", "identificar_relacao"},
    "comparar": {"comparar"},
    "encontrar_erro": {"encontrar_erro"},
    "justificar": {"justificativa"},
}


def filtrar(
    area: str | None = None,
    assunto: str | None = None,
    dificuldade: str | None = None,
    tipos: Iterable[str] | None = None,
    excluir: Iterable[str] = (),
) -> list[QuestaoSchema]:
    tipos = set(tipos) if tipos else None
    excluir = set(excluir)
    return [
        q
        for q in carregar_questoes()
        if (area is None or q.area == area)
        and (assunto is None or q.assunto == assunto)
        and (dificuldade is None or q.dificuldade == dificuldade)
        and (tipos is None or q.tipo in tipos)
        and q.id not in excluir
    ]


def sortear(candidatas: list[QuestaoSchema], s: Session | None = None, rng: random.Random | None = None) -> QuestaoSchema | None:
    """Sorteia priorizando questões ainda não respondidas."""
    if not candidatas:
        return None
    rng = rng or random.Random()
    if s is not None:
        respondidas = set(s.scalars(select(Tentativa.questao_id).distinct()))
        novas = [q for q in candidatas if q.id not in respondidas]
        if novas:
            return rng.choice(novas)
    return rng.choice(candidatas)


def semelhante(q: QuestaoSchema, s: Session | None = None, excluir: Iterable[str] = ()) -> QuestaoSchema | None:
    """Outra questão do mesmo assunto (variação da mesma regra em outro contexto)."""
    excl = set(excluir) | {q.id}
    cands = filtrar(assunto=q.assunto, excluir=excl)
    if not cands:
        cands = filtrar(area=q.area, excluir=excl)
    return sortear(cands, s)


# --------------------------------------------------------------------------- #
# Correção
# --------------------------------------------------------------------------- #


@dataclass
class Correcao:
    correta: bool | None  # None = depende de avaliação (justificativa aberta)
    resposta_registrada: str
    detalhes: dict


def corrigir(q: QuestaoSchema, resposta: str | dict[str, str]) -> Correcao:
    if q.tipo == "associacao":
        if not isinstance(resposta, dict):
            raise ValueError("associação exige um dicionário item → resposta")
        acertos = {p.item: resposta.get(p.item) == p.resposta for p in q.pares}
        registro = "; ".join(f"{p.item}={resposta.get(p.item, '')}" for p in q.pares)
        return Correcao(all(acertos.values()), registro, {"por_item": acertos})

    if q.tipo == "justificativa":
        texto = str(resposta).strip()
        if not texto:
            raise ValueError("resposta vazia")
        norm = normalizar(texto)
        presentes = [k for k in q.palavras_chave if normalizar(k) in norm]
        return Correcao(None, texto, {"palavras_chave_presentes": presentes, "palavras_chave": q.palavras_chave})

    letra = str(resposta).strip()
    if letra not in q.letras:
        raise ValueError(f"alternativa '{letra}' inexistente")
    return Correcao(letra == q.resposta, letra, {})


# --------------------------------------------------------------------------- #
# Persistência
# --------------------------------------------------------------------------- #


def registrar_tentativa(
    s: Session,
    q: QuestaoSchema,
    resposta_registrada: str,
    correta: bool | None,
    tempo_resposta: float | None = None,
    modo: str = "treino",
    simulado_id: int | None = None,
    quando: datetime | None = None,
) -> Tentativa:
    t = Tentativa(
        questao_id=q.id,
        resposta_usuario=resposta_registrada,
        correta=correta,
        tempo_resposta=max(0.0, tempo_resposta) if tempo_resposta is not None else None,
        modo=modo,
        simulado_id=simulado_id,
        data=quando or datetime.now(),
    )
    s.add(t)
    s.flush()
    if correta is not None:
        revision_service.registrar_resultado(s, q.assunto, correta, (quando or datetime.now()).date())
    return t


def avaliar_tentativa(s: Session, tentativa_id: int, correta: bool) -> Tentativa:
    """Fecha uma tentativa pendente (autoavaliação ou avaliação por IA)."""
    t = s.get(Tentativa, tentativa_id)
    if t is None:
        raise ValueError("tentativa inexistente")
    ja_avaliada = t.correta is not None
    t.correta = correta
    q = questao_por_id(t.questao_id)
    if q and not ja_avaliada:
        revision_service.registrar_resultado(s, q.assunto, correta, t.data.date())
    s.flush()
    return t


def questoes_com_erro_pendente(s: Session) -> list[tuple[QuestaoSchema, Tentativa]]:
    """Questões cuja tentativa mais recente foi incorreta."""
    sub = (
        select(Tentativa.questao_id, func.max(Tentativa.id).label("ultima"))
        .where(Tentativa.correta.is_not(None))
        .group_by(Tentativa.questao_id)
        .subquery()
    )
    ultimas = s.scalars(select(Tentativa).join(sub, Tentativa.id == sub.c.ultima).where(Tentativa.correta.is_(False)).order_by(Tentativa.data.desc()))
    out = []
    for t in ultimas:
        q = questao_por_id(t.questao_id)
        if q:
            out.append((q, t))
    return out


def tentativas_pendentes_avaliacao(s: Session) -> list[Tentativa]:
    return list(s.scalars(select(Tentativa).where(Tentativa.correta.is_(None)).order_by(Tentativa.data.desc())))


def ultimo_assunto_estudado(s: Session) -> str | None:
    t = s.scalar(select(Tentativa).order_by(Tentativa.data.desc()).limit(1))
    if not t:
        return None
    q = questao_por_id(t.questao_id)
    return q.assunto if q else None


# --------------------------------------------------------------------------- #
# Simulados
# --------------------------------------------------------------------------- #


def montar_simulado(
    n: int, area: str | None = None, dificuldade: str | None = None, rng: random.Random | None = None
) -> list[QuestaoSchema]:
    rng = rng or random.Random()
    cands = [q for q in filtrar(area=area, dificuldade=dificuldade) if q.tipo != "justificativa"]
    rng.shuffle(cands)
    return cands[:n]


def iniciar_simulado(s: Session, total: int, area: str | None, dificuldade: str | None) -> Simulado:
    sim = Simulado(total=total, area_id=area, dificuldade=dificuldade, acertos=0)
    s.add(sim)
    s.flush()
    return sim


def concluir_simulado(s: Session, simulado_id: int) -> Simulado:
    sim = s.get(Simulado, simulado_id)
    if sim is None:
        raise ValueError("simulado inexistente")
    sim.acertos = sum(1 for t in sim.tentativas if t.correta)
    sim.total = max(sim.total, len(sim.tentativas))
    sim.concluido_em = datetime.now()
    s.flush()
    return sim


def hoje() -> date:
    return date.today()
