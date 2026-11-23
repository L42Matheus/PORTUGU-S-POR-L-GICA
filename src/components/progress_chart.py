"""Gráficos simples (Plotly) para o painel de desempenho."""

from __future__ import annotations

import pandas as pd
import plotly.express as px

AZUL = "#1d4ed8"


def _layout(fig):
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=320, yaxis_tickformat=".0%")
    return fig


def barras_taxa(df: pd.DataFrame, titulo: str):
    fig = px.bar(
        df,
        x="rotulo",
        y="taxa",
        text=df.apply(lambda r: f"{r['taxa']:.0%} ({int(r['acertos'])}/{int(r['tentativas'])})", axis=1),
        title=titulo,
        labels={"rotulo": "", "taxa": "Taxa de acertos"},
        color_discrete_sequence=[AZUL],
    )
    fig.update_yaxes(range=[0, 1.05])
    return _layout(fig)


def linha_semanal(df: pd.DataFrame):
    df = df.assign(semana=pd.to_datetime(df["semana"]).dt.strftime("%d/%m/%Y"))
    fig = px.line(
        df,
        x="semana",
        y="taxa",
        markers=True,
        title="Evolução semanal da taxa de acertos",
        labels={"semana": "Semana (início)", "taxa": "Taxa de acertos"},
        hover_data={"tentativas": True, "acertos": True},
        color_discrete_sequence=[AZUL],
    )
    fig.update_yaxes(range=[0, 1.05])
    return _layout(fig)


def linha_simulados(df: pd.DataFrame):
    fig = px.line(
        df,
        x="data",
        y="taxa",
        markers=True,
        title="Histórico de simulados",
        labels={"data": "Data", "taxa": "Taxa de acertos"},
        hover_data={"total": True, "acertos": True, "area": True},
        color_discrete_sequence=[AZUL],
    )
    fig.update_yaxes(range=[0, 1.05])
    return _layout(fig)
