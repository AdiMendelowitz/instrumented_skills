"""Keep test writes/deletions inside the brief's permitted temporary root."""
import os
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\REDACTED_USER\venvs\token-aware-eval\tmp")
ROOT.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(ROOT), TMP=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
tempfile.tempdir = str(ROOT)


def pytest_configure(config):
    import pytest
    base = Path(config.option.basetemp).resolve()
    if not base.is_relative_to(ROOT.resolve()) or base == ROOT.resolve():
        raise pytest.UsageError("pytest basetemp must be strictly inside the brief's temporary root")


import pytest  # ADR-16 fixture below


@pytest.fixture(autouse=True)
def _adr16_synthetic_oauth_token(tmp_path_factory, monkeypatch):
    """ADR-16: every test sees a synthetic token file and no outranking credential variables."""
    import runlib
    token_file = tmp_path_factory.mktemp("adr16-token") / "oauth-token.txt"
    token_file.write_text("synthetic-oauth-token-0123456789", encoding="utf-8")
    monkeypatch.setattr(runlib, "OAUTH_TOKEN_FILE", token_file)
    for name in runlib.OUTRANKING_ENV:
        monkeypatch.delenv(name, raising=False)
    for name in [n for n in os.environ if n.upper().startswith("CODEX_")]:  # ADR-18
        monkeypatch.delenv(name, raising=False)
