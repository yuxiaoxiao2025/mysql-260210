from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SkillsCliResult:
    ok: bool
    message: str
    command: str
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    install_commands: list[str] | None = None
    link: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_URL_RE = re.compile(r"https?://\\S+")


def _ensure_npx_available() -> bool:
    return shutil.which("npx") is not None


def _run_npx(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _extract_install_commands(stdout: str) -> list[str]:
    cmds: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("npx skills add "):
            cmds.append(line)
    return cmds


def _extract_first_link(stdout: str) -> str | None:
    m = _URL_RE.search(stdout)
    return m.group(0) if m else None


def find_skills(query: str) -> SkillsCliResult:
    command = f'npx skills find "{query}"'
    if not _ensure_npx_available():
        return SkillsCliResult(
            ok=False,
            message="当前环境未检测到 npx（需要 Node.js/npm）。请先安装 Node.js 后重试，或在本地终端手动运行命令。",
            command=command,
            error="npx_not_found",
        )

    try:
        cp = _run_npx(["npx", "skills", "find", query])
    except FileNotFoundError:
        return SkillsCliResult(
            ok=False,
            message="当前环境无法执行 npx。请确认 Node.js/npm 已正确安装并加入 PATH。",
            command=command,
            error="npx_file_not_found",
        )

    if cp.returncode != 0:
        return SkillsCliResult(
            ok=False,
            message="skills 查找执行失败。你可以在本地终端手动运行命令复现并查看完整错误输出。",
            command=command,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            error=f"exit_code_{cp.returncode}",
        )

    install_cmds = _extract_install_commands(cp.stdout or "")
    link = _extract_first_link(cp.stdout or "")
    return SkillsCliResult(
        ok=True,
        message="skills 查找已完成。",
        command=command,
        stdout=cp.stdout or "",
        stderr=cp.stderr or "",
        install_commands=install_cmds or None,
        link=link,
    )


def install_skill(spec: str, global_install: bool = True) -> SkillsCliResult:
    cmd_parts = ["npx", "skills", "add", spec]
    if global_install:
        cmd_parts += ["-g", "-y"]
    command = " ".join(cmd_parts)

    if not _ensure_npx_available():
        return SkillsCliResult(
            ok=False,
            message="当前环境未检测到 npx（需要 Node.js/npm）。请先安装 Node.js 后重试，或在本地终端手动运行命令。",
            command=command,
            error="npx_not_found",
        )

    try:
        cp = _run_npx(cmd_parts)
    except FileNotFoundError:
        return SkillsCliResult(
            ok=False,
            message="当前环境无法执行 npx。请确认 Node.js/npm 已正确安装并加入 PATH。",
            command=command,
            error="npx_file_not_found",
        )

    if cp.returncode != 0:
        return SkillsCliResult(
            ok=False,
            message="skill 安装执行失败。你可以在本地终端手动运行命令复现并查看完整错误输出。",
            command=command,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            error=f"exit_code_{cp.returncode}",
        )

    return SkillsCliResult(
        ok=True,
        message="skill 安装命令已执行完成。",
        command=command,
        stdout=cp.stdout or "",
        stderr=cp.stderr or "",
    )

