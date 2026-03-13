import subprocess

import pytest

from src.skills.skills_cli import find_skills, install_skill


def test_find_skills_graceful_when_npx_missing(monkeypatch):
    monkeypatch.setattr("src.skills.skills_cli.shutil.which", lambda name: None)
    out = find_skills("mysql index")
    assert out.ok is False
    assert "npx" in out.message.lower()
    assert out.error == "npx_not_found"
    assert "npx skills find" in out.command


def test_install_skill_graceful_when_npx_missing(monkeypatch):
    monkeypatch.setattr("src.skills.skills_cli.shutil.which", lambda name: None)
    out = install_skill("some-skill")
    assert out.ok is False
    assert out.error == "npx_not_found"
    assert "npx skills add" in out.command


def test_find_skills_graceful_when_command_fails(monkeypatch):
    monkeypatch.setattr("src.skills.skills_cli.shutil.which", lambda name: "npx")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="oops", stderr="bad")

    monkeypatch.setattr("src.skills.skills_cli._run_npx", fake_run)
    out = find_skills("mysql index")
    assert out.ok is False
    assert "失败" in out.message
    assert out.stdout == "oops"
    assert out.stderr == "bad"


def test_install_skill_graceful_when_command_fails(monkeypatch):
    monkeypatch.setattr("src.skills.skills_cli.shutil.which", lambda name: "npx")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=2, stdout="nope", stderr="err")

    monkeypatch.setattr("src.skills.skills_cli._run_npx", fake_run)
    out = install_skill("some-skill", global_install=True)
    assert out.ok is False
    assert out.error == "exit_code_2"
    assert out.stdout == "nope"
    assert out.stderr == "err"

