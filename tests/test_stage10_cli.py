"""Stage 10: no-network CLI smoke tests for the *existing* Stage 09 agent.

These tests do not call an external API; they require the local sample assets
already available to the user for --check-local.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_stable_main_entry_exists() -> None:
    assert (ROOT / "main.py").is_file()
    assert callable(__import__("main").main)


def test_main_delegates_to_existing_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    import main
    from metso_agent.agent import chat
    calls: list[str] = []
    monkeypatch.setattr(chat, "main", lambda: calls.append("delegate"))
    main.main()
    assert calls == ["delegate"]


def test_help_exposes_local_and_external_modes() -> None:
    result = run_cli("--help")
    assert result.returncode == 0, result.stderr
    assert "--check-local" in result.stdout
    assert "--allow-external-evidence" in result.stdout


def test_help_exposes_verbose_and_private_logging() -> None:
    result = run_cli("--help")
    assert result.returncode == 0, result.stderr
    assert "--verbose" in result.stdout
    assert "--session-log" in result.stdout  # Stage 09 reliability fix


def test_cli_rejects_external_mode_without_opt_in() -> None:
    result = run_cli()
    assert result.returncode != 0
    assert "--allow-external-evidence" in result.stderr


def test_local_preflight_succeeds_without_api() -> None:
    result = run_cli("--check-local")
    assert result.returncode == 0, result.stderr
    assert "Product retrieval usable: True" in result.stdout
    assert "Service ledger readable: 50 reports" in result.stdout
    assert "without external API calls" in result.stdout


def test_walkthrough_document_is_present() -> None:
    p = ROOT / "docs" / "stage10_cli_walkthrough.md"
    assert p.is_file()
    txt = p.read_text(encoding="utf-8")
    assert "--check-local" in txt
    assert "--session-log" in txt
    assert "--allow-external-evidence" in txt
