"""Estatísticas derivadas exclusivamente das tentativas registradas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.models import Simulado, Tentativa
from src.services.content_service import nome_area, nome_assunto, questao_por_id

COLUNAS = ["id", "data", "questao_id", "area", "assunto", "dificuldade", "correta", "tempo", "modo"]


def tentativas_df(s: Session) -> pd.DataFrame:
    linhas = []
    for t in s.scalars(select(Tentativa).order_by(Tentativa.data)):
        q = questao_por_id(t.questao_id)
        linhas.append(
            {
                "id": t.id,
                "data": t.data,
                "questao_id": t.questao_id,
                "area": q.area if q else None,
                "assunto": q.assunto if q else None,
                "dificuldade": q.dificuldade if q else None,
                "correta": t.correta,
                "tempo": t.tempo_resposta,
                "modo": t.modo,
            }
        )
    return pd.DataFrame(linhas, columns=COLUNAS)


def filtrar(
    df: pd.DataFrame,
    area: str | None = None,
    assunto: str | None = None,
    dificuldade: str | None = None,
    desde: date | None = None,
    ate: date | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    m = pd.Series(True, index=df.index)
    if area:
        m &= df["area"] == area
    if assunto:
        m &= df["assunto"] == assunto
    if dificuldade:
        m &= df["dificuldade"] == dificuldade
    if desde:
        m &= df["data"] >= datetime.combine(desde, datetime.min.time())
    if ate:
        m &= df["data"] < datetime.combine(ate + timedelta(days=1), datetime.min.time())
    return df[m]


@dataclass
class Resumo:
    resolvidas: int
    avaliadas: int
    acertos: int
    taxa: float | None
    tempo_total_min: float
    pendentes_avaliacao: int


def resumo(df: pd.DataFrame) -> Resumo:
    if df.empty:
        return Resumo(0, 0, 0, None, 0.0, 0)
    avaliadas = df[df["correta"].notna()]
    acertos = int((avaliadas["correta"] == True).sum())  # noqa: E712
    taxa = acertos / len(avaliadas) if len(avaliadas) else None
    tempo = float(df["tempo"].fillna(0).sum()) / 60
    return Resumo(len(df), len(avaliadas), acertos, taxa, round(tempo, 1), int(df["correta"].isna().sum()))


def _taxa_por(df: pd.DataFrame, coluna: str, rotulo) -> pd.DataFrame:
    av = df[df["correta"].notna()].copy()
    if av.empty:
        return pd.DataFrame(columns=[coluna, "rotulo", "tentativas", "acertos", "taxa"])
    av["acerto"] = av["correta"].astype(bool).astype(int)
    g = av.groupby(coluna).agg(tentativas=("acerto", "size"), acertos=("acerto", "sum")).reset_index()
    g["taxa"] = g["acertos"] / g["tentativas"]
    g["rotulo"] = g[coluna].map(rotulo)
    return g


def por_area(df: pd.DataFrame) -> pd.DataFrame:
    return _taxa_por(df, "area", nome_area)


def por_dificuldade(df: pd.DataFrame) -> pd.DataFrame:
    nomes = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}
    g = _taxa_por(df, "dificuldade", lambda d: nomes.get(d, d))
    ordem = {"iniciante": 0, "intermediario": 1, "avancado": 2}
    return g.sort_values("dificuldade", key=lambda c: c.map(ordem)) if not g.empty else g


def assuntos_dificeis(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    g = _taxa_por(df, "assunto", nome_assunto)
    if g.empty:
        return g
    return g.sort_values(["taxa", "tentativas"], ascending=[True, False]).head(n)


def evolucao_semanal(df: pd.DataFrame) -> pd.DataFrame:
    av = df[df["correta"].notna()].copy()
    if av.empty:
        return pd.DataFrame(columns=["semana", "tentativas", "acertos", "taxa"])
    av["semana"] = pd.to_datetime(av["data"]).dt.to_period("W-SUN").dt.start_time.dt.date
    av["acerto"] = av["correta"].astype(bool).astype(int)
    g = av.groupby("semana").agg(tentativas=("acerto", "size"), acertos=("acerto", "sum")).reset_index()
    g["taxa"] = g["acertos"] / g["tentativas"]
    return g


def sequencia_dias(datas: list[date], hoje: date | None = None) -> int:
    """Dias consecutivos de estudo terminando hoje (ou ontem, se hoje ainda não houve estudo)."""
    hoje = hoje or date.today()
    dias = set(datas)
    if not dias:
        return 0
    cursor = hoje if hoje in dias else hoje - timedelta(days=1)
    seq = 0
    while cursor in dias:
        seq += 1
        cursor -= timedelta(days=1)
    return seq


def sequencia(df: pd.DataFrame, hoje: date | None = None) -> int:
    if df.empty:
        return 0
    return sequencia_dias([d.date() for d in pd.to_datetime(df["data"])], hoje)


def historico_simulados(s: Session) -> pd.DataFrame:
    linhas = [
        {
            "id": sim.id,
            "data": sim.iniciado_em,
            "area": nome_area(sim.area_id) if sim.area_id else "Todas",
            "dificuldade": sim.dificuldade or "Todas",
            "total": sim.total,
            "acertos": sim.acertos,
            "taxa": sim.acertos / sim.total if sim.total else None,
        }
        for sim in s.scalars(select(Simulado).where(Simulado.concluido_em.is_not(None)).order_by(Simulado.iniciado_em))
    ]
    return pd.DataFrame(linhas, columns=["id", "data", "area", "dificuldade", "total", "acertos", "taxa"])
