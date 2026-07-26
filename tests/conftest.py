"""Shared pytest fixtures."""

import pytest


@pytest.fixture(autouse=True)
def isolated_harnext_home(tmp_path, monkeypatch):
    """
    Never let tests touch the real ~/.harnext. src.harnext_bootstrap reads
    HARNEXT_HOME (falling back to ~/.harnext) whenever a Coordinator is
    constructed, so redirect it to a per-test tmp dir for every test.
    """
    monkeypatch.setenv("HARNEXT_HOME", str(tmp_path / ".harnext"))
    monkeypatch.setenv("HARNEXT_AGENT_DIR", str(tmp_path / ".harnext" / "agent"))
