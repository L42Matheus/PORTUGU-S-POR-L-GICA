"""Carregamento e validação dos conteúdos didáticos (JSON em ``data/``).

Os arquivos JSON são a fonte da verdade. Na inicialização, eles são
validados com Pydantic e espelhados no banco (para integridade referencial).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from src.core import models
from src.core.schemas import AreaSchema, Licao, QuestaoSchema, RoteiroTutor

DATA = Path(__file__).resolve().parents[2] / "data"


class ConteudoInvalido(ValueError):
    pass


def _ler_json(caminho: Path):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - erro de autoria
        raise ConteudoInvalido(f"JSON inválido em {caminho.name}: {exc}") from exc


@lru_cache(maxsize=1)
def carregar_areas() -> tuple[AreaSchema, ...]:
    areas = [AreaSchema.model_validate(a) for a in _ler_json(DATA / "areas.json")]
    return tuple(sorted(areas, key=lambda a: a.ordem))


def mapa_assuntos() -> dict[str, tuple[AreaSchema, str]]:
    """assunto_id -> (área, nome do assunto)."""
    return {s.id: (a, s.nome) for a in carregar_areas() for s in a.assuntos}


def nome_assunto(assunto_id: str) -> str:
    return mapa_assuntos().get(assunto_id, (None, assunto_id))[1]


def nome_area(area_id: str) -> str:
    return next((a.nome for a in carregar_areas() if a.id == area_id), area_id)


@lru_cache(maxsize=1)
def carregar_licoes() -> tuple[Licao, ...]:
    licoes: list[Licao] = []
    for arq in sorted((DATA / "lessons").glob("*.json")):
        licoes.extend(Licao.model_validate(x) for x in _ler_json(arq))
    assuntos = mapa_assuntos()
    for lic in licoes:
        if lic.assunto not in assuntos:
            raise ConteudoInvalido(f"Lição {lic.id} referencia assunto inexistente {lic.assunto}")
        if assuntos[lic.assunto][0].id != lic.area:
            raise ConteudoInvalido(f"Lição {lic.id}: área incompatível com o assunto")
    return tuple(licoes)


def licao_do_assunto(assunto_id: str) -> Licao | None:
    return next((lic for lic in carregar_licoes() if lic.assunto == assunto_id), None)


@lru_cache(maxsize=1)
def carregar_questoes() -> tuple[QuestaoSchema, ...]:
    questoes: list[QuestaoSchema] = []
    for arq in sorted((DATA / "questions").glob("*.json")):
        questoes.extend(QuestaoSchema.model_validate(x) for x in _ler_json(arq))
    ids = [q.id for q in questoes]
    if len(ids) != len(set(ids)):
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        raise ConteudoInvalido(f"IDs de questão repetidos: {repetidos}")
    assuntos = mapa_assuntos()
    for q in questoes:
        if q.assunto not in assuntos:
            raise ConteudoInvalido(f"Questão {q.id} referencia assunto inexistente {q.assunto}")
        if assuntos[q.assunto][0].id != q.area:
            raise ConteudoInvalido(f"Questão {q.id}: área '{q.area}' incompatível com o assunto")
    return tuple(questoes)


def questao_por_id(qid: str) -> QuestaoSchema | None:
    return next((q for q in carregar_questoes() if q.id == qid), None)


@lru_cache(maxsize=1)
def carregar_roteiros() -> tuple[RoteiroTutor, ...]:
    return tuple(RoteiroTutor.model_validate(x) for x in _ler_json(DATA / "tutor" / "roteiros.json"))


def sincronizar_conteudo(s: Session) -> None:
    """Espelha áreas, assuntos, lições e questões no banco.

    Questões removidas dos JSON não são apagadas (podem ter tentativas):
    ficam marcadas como inativas.
    """
    for area in carregar_areas():
        s.merge(models.AreaEstudo(id=area.id, nome=area.nome, descricao=area.descricao, ordem=area.ordem))
        for sub in area.assuntos:
            s.merge(models.Assunto(id=sub.id, area_id=area.id, nome=sub.nome, nivel=sub.nivel))
    s.flush()

    for lic in carregar_licoes():
        s.merge(
            models.Conteudo(
                id=lic.id,
                assunto_id=lic.assunto,
                titulo=lic.titulo,
                explicacao=lic.conceito,
                exemplos=[e.model_dump() for e in lic.exemplos],
                regras=list(lic.regras),
            )
        )

    ativos = set()
    for q in carregar_questoes():
        ativos.add(q.id)
        s.merge(
            models.Questao(
                id=q.id,
                assunto_id=q.assunto,
                tipo=q.tipo,
                enunciado=q.enunciado,
                texto_base=q.texto_base,
                alternativas=[a.model_dump() for a in q.alternativas] or [p.model_dump() for p in q.pares],
                resposta=q.resposta,
                justificativa=q.justificativa,
                dificuldade=q.dificuldade,
                ativa=True,
            )
        )
    for antiga in s.query(models.Questao).filter(models.Questao.id.not_in(ativos)):
        antiga.ativa = False
