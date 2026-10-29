"""run_cmd writes one log entry per command, with the exit status in the header
so the GUI log viewer can show ok / failed / timed out without guessing."""

from __future__ import annotations

import subprocess
import types

from core import executor


def _fake_run(returncode: int, stdout: str = "", stderr: str = ""):
    def run(*args, **kwargs):
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return run


def test_exit_code_is_written_into_the_header(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(3, stdout="80/tcp open http\n"))
    logfile = tmp_path / "results" / "logs" / "chain_t.log"
    executor.run_cmd("nmap -sV 10.0.0.5", str(logfile))
    lines = logfile.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(" ")[-1] == "exit=3"
    assert lines[1] == "$ nmap -sV 10.0.0.5"
    assert "80/tcp open http" in logfile.read_text(encoding="utf-8")


def test_successful_command_is_marked_exit_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout="done\n"))
    logfile = tmp_path / "chain_t.log"
    executor.run_cmd("nmap -sn 10.0.0.5", str(logfile))
    assert logfile.read_text(encoding="utf-8").splitlines()[0].endswith("exit=0")


def test_timeout_is_logged_instead_of_lost(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=5)
    monkeypatch.setattr(subprocess, "run", timeout)
    logfile = tmp_path / "chain_t.log"
    output, code = executor.run_cmd("evil-winrm -i 10.0.0.5", str(logfile), timeout=5)
    assert code == 1
    text = logfile.read_text(encoding="utf-8")
    assert text.splitlines()[0].endswith("exit=timeout")
    assert "(killed after 5s)" in text
