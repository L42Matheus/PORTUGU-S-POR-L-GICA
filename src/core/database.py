"""Conexão, migrações e sessões do banco SQLite."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from src.core.models import Base, SchemaVersion

RAIZ = Path(__file__).resolve().parents[2]
DB_PADRAO = RAIZ / "data" / "estudos.db"


def url_padrao() -> str:
    return os.getenv("PPL_DATABASE_URL") or f"sqlite:///{DB_PADRAO}"


def criar_engine(url: str | None = None) -> Engine:
    url = url or url_padrao()
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _ativar_fk(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


# --------------------------------------------------------------------------- #
# Migrações
# --------------------------------------------------------------------------- #
# Cada migração recebe uma conexão já dentro de transação. Novas versões devem
# ser acrescentadas ao final da lista, nunca editadas depois de publicadas.


def _m001_esquema_inicial(conn: Connection) -> None:
    Base.metadata.create_all(conn)


MIGRACOES: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "Esquema inicial", _m001_esquema_inicial),
]


def migrar(engine: Engine) -> int:
    """Aplica as migrações pendentes e devolve a versão final do esquema."""
    SchemaVersion.__table__.create(engine, checkfirst=True)
    with engine.begin() as conn:
        aplicadas = set(conn.execute(select(SchemaVersion.version)).scalars())
        for versao, descricao, funcao in MIGRACOES:
            if versao in aplicadas:
                continue
            funcao(conn)
            conn.execute(
                SchemaVersion.__table__.insert().values(version=versao, descricao=descricao)
            )
            aplicadas.add(versao)
    return max(aplicadas)


def fabrica_sessoes(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def sessao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    s = fabrica()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def inicializar(url: str | None = None) -> tuple[Engine, sessionmaker[Session]]:
    """Cria o engine, migra o esquema e sincroniza o conteúdo didático."""
    from src.services.content_service import sincronizar_conteudo

    engine = criar_engine(url)
    migrar(engine)
    fabrica = fabrica_sessoes(engine)
    with sessao(fabrica) as s:
        sincronizar_conteudo(s)
    return engine, fabrica
