"""Modelo de dados (SQLAlchemy 2.x).

Duas famílias de tabelas:

* Conteúdo didático (AreaEstudo, Assunto, Conteudo, Questao): espelho dos
  arquivos JSON em ``data/``. Os JSON são a fonte da verdade; o banco guarda
  uma cópia para garantir integridade referencial das tentativas.
* Dados de estudo (Tentativa, Revisao, Simulado, AnaliseTexto): produzidos
  pelo estudante e nunca sobrescritos pela sincronização de conteúdo.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def agora() -> datetime:
    return datetime.now()


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    """Controle de migrações aplicadas."""

    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    descricao: Mapped[str] = mapped_column(String(200))
    aplicada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class AreaEstudo(Base):
    __tablename__ = "area_estudo"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, default="")
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    assuntos: Mapped[list[Assunto]] = relationship(back_populates="area")


class Assunto(Base):
    __tablename__ = "assunto"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    area_id: Mapped[str] = mapped_column(
        ForeignKey("area_estudo.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    nivel: Mapped[str] = mapped_column(String(20), default="iniciante")

    area: Mapped[AreaEstudo] = relationship(back_populates="assuntos")
    conteudos: Mapped[list[Conteudo]] = relationship(back_populates="assunto")
    questoes: Mapped[list[Questao]] = relationship(back_populates="assunto")
    revisao: Mapped[Revisao | None] = relationship(back_populates="assunto")


class Conteudo(Base):
    __tablename__ = "conteudo"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    assunto_id: Mapped[str] = mapped_column(
        ForeignKey("assunto.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    explicacao: Mapped[str] = mapped_column(Text, nullable=False)
    exemplos: Mapped[list] = mapped_column(JSON, default=list)
    regras: Mapped[list] = mapped_column(JSON, default=list)

    assunto: Mapped[Assunto] = relationship(back_populates="conteudos")


class Questao(Base):
    __tablename__ = "questao"
    __table_args__ = (
        CheckConstraint(
            "dificuldade IN ('iniciante', 'intermediario', 'avancado')",
            name="ck_questao_dificuldade",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    assunto_id: Mapped[str] = mapped_column(
        ForeignKey("assunto.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    texto_base: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternativas: Mapped[list] = mapped_column(JSON, default=list)
    resposta: Mapped[str] = mapped_column(Text, nullable=False)
    justificativa: Mapped[str] = mapped_column(Text, nullable=False)
    dificuldade: Mapped[str] = mapped_column(String(20), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    assunto: Mapped[Assunto] = relationship(back_populates="questoes")
    tentativas: Mapped[list[Tentativa]] = relationship(back_populates="questao")


class Simulado(Base):
    __tablename__ = "simulado"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    area_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dificuldade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    acertos: Mapped[int] = mapped_column(Integer, default=0)

    tentativas: Mapped[list[Tentativa]] = relationship(back_populates="simulado")


class Tentativa(Base):
    __tablename__ = "tentativa"
    __table_args__ = (
        CheckConstraint("tempo_resposta IS NULL OR tempo_resposta >= 0", name="ck_tempo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    questao_id: Mapped[str] = mapped_column(
        ForeignKey("questao.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    resposta_usuario: Mapped[str] = mapped_column(Text, nullable=False)
    # ``None`` = autoavaliação pendente (justificativa aberta sem IA).
    correta: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    data: Mapped[datetime] = mapped_column(DateTime, default=agora, index=True)
    tempo_resposta: Mapped[float | None] = mapped_column(Float, nullable=True)
    modo: Mapped[str] = mapped_column(String(30), default="treino")
    simulado_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulado.id", ondelete="SET NULL"), nullable=True
    )

    questao: Mapped[Questao] = relationship(back_populates="tentativas")
    simulado: Mapped[Simulado | None] = relationship(back_populates="tentativas")


class Revisao(Base):
    """Estado da revisão espaçada de um assunto."""

    __tablename__ = "revisao"
    __table_args__ = (UniqueConstraint("assunto_id", name="uq_revisao_assunto"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assunto_id: Mapped[str] = mapped_column(
        ForeignKey("assunto.id", ondelete="CASCADE"), nullable=False
    )
    proxima_data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    intervalo: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    etapa: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    ultima_revisao: Mapped[date | None] = mapped_column(Date, nullable=True)
    acertos: Mapped[int] = mapped_column(Integer, default=0)
    erros: Mapped[int] = mapped_column(Integer, default=0)
    # Taxa de acertos observada (0 a 1) — derivada das tentativas registradas.
    desempenho: Mapped[float] = mapped_column(Float, default=0.0)

    assunto: Mapped[Assunto] = relationship(back_populates="revisao")


class AnaliseTexto(Base):
    __tablename__ = "analise_texto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    texto_original: Mapped[str] = mapped_column(Text, nullable=False)
    modalidade: Mapped[str] = mapped_column(String(40), nullable=False)
    origem: Mapped[str] = mapped_column(String(30), nullable=False)
    resultado: Mapped[dict] = mapped_column(JSON, default=dict)
    data: Mapped[datetime] = mapped_column(DateTime, default=agora)
