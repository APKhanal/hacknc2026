import pytest


@pytest.fixture(autouse=True)
def no_live_database(monkeypatch):
    """create_app loads the root .env, which may hold a real DATABASE_URL: tests always use code defaults."""
    monkeypatch.setenv("SETTINGS_SOURCE", "code")
    monkeypatch.setenv("DATABASE_URL", "")
