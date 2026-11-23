"""Geração de feedback pedagógico a partir do conteúdo revisado."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.schemas import QuestaoSchema
from src.services.content_service import nome_assunto
from src.services.question_service import Correcao


@dataclass
class Feedback:
    correta: bool | None
    titulo: str
    explicacao: str
    regra: str
    escolhida: str | None = None
    resposta_correta: str | None = None
    diagnostico: str | None = None
    observacao: str | None = None
    exemplos: list[str] = field(default_factory=list)
    detalhes_associacao: dict[str, bool] = field(default_factory=dict)
    assunto: str = ""


def _texto_alt(q: QuestaoSchema, letra: str) -> str:
    alt = q.alternativa(letra)
    return f"{letra}) {alt.texto}" if alt else letra


def gerar(q: QuestaoSchema, correcao: Correcao) -> Feedback:
    assunto = nome_assunto(q.assunto)

    if q.tipo == "justificativa":
        presentes = correcao.detalhes.get("palavras_chave_presentes", [])
        faltando = [k for k in q.palavras_chave if k not in presentes]
        obs = (
            "Sua resposta menciona os conceitos-chave esperados."
            if not faltando
            else "Conceitos de referência que não apareceram na sua resposta: " + ", ".join(f"'{k}'" for k in faltando) + "."
        )
        return Feedback(
            correta=None,
            titulo="Compare sua justificativa com a resposta modelo",
            explicacao=q.resposta,
            regra=q.regra,
            observacao=obs + " A verificação de palavras-chave é só um apoio: avalie se o raciocínio está correto, não apenas se as palavras aparecem.",
            exemplos=q.exemplos_relacionados,
            assunto=assunto,
        )

    if q.tipo == "associacao":
        por_item = correcao.detalhes.get("por_item", {})
        gabarito = "; ".join(f"{p.item} → {p.resposta}" for p in q.pares)
        if correcao.correta:
            return Feedback(True, "Associação correta!", q.justificativa, q.regra, observacao="Tente explicar em voz alta o critério de cada associação.", exemplos=q.exemplos_relacionados, detalhes_associacao=por_item, assunto=assunto)
        erradas = [i for i, ok in por_item.items() if not ok]
        return Feedback(
            False,
            "Algumas associações estão incorretas",
            q.justificativa,
            q.regra,
            resposta_correta=gabarito,
            diagnostico="Revise: " + ", ".join(f"'{i}'" for i in erradas) + ".",
            exemplos=q.exemplos_relacionados,
            detalhes_associacao=por_item,
            assunto=assunto,
        )

    escolhida = correcao.resposta_registrada
    if correcao.correta:
        return Feedback(
            True,
            "Correto!",
            q.justificativa,
            q.regra,
            escolhida=_texto_alt(q, escolhida),
            observacao=(q.exemplos_relacionados[0] and f"Para fixar, aplique a mesma regra em: {q.exemplos_relacionados[0]}") if q.exemplos_relacionados else None,
            exemplos=q.exemplos_relacionados,
            assunto=assunto,
        )

    alt = q.alternativa(escolhida)
    diagnostico = alt.comentario if alt and alt.comentario else f"A alternativa escolhida não aplica corretamente a regra de {assunto.lower()}."
    return Feedback(
        False,
        "Ainda não",
        q.justificativa,
        q.regra,
        escolhida=_texto_alt(q, escolhida),
        resposta_correta=_texto_alt(q, q.resposta),
        diagnostico=diagnostico,
        exemplos=q.exemplos_relacionados,
        assunto=assunto,
    )
