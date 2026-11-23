import pytest

from src.core.database import inicializar, sessao


@pytest.fixture()
def fabrica(tmp_path):
    _, fab = inicializar(f"sqlite:///{tmp_path / 'teste.db'}")
    return fab


@pytest.fixture()
def s(fabrica):
    with sessao(fabrica) as sess:
        yield sess


@pytest.fixture(autouse=True)
def sem_ia(monkeypatch):
    """Garante que nenhum teste dependa de chave real de API."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("PPL_AI_PROVIDER", "none")
