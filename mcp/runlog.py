# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-run log files for the MCP Ansible runners.

Each run streams its output to <root>/logs/<timestamp>-<label>.log while it is
still running, and repoints <root>/logs/latest.log at it, so that a
`tail -F logs/latest.log` left open in a terminal shows what the MCP tools are
doing instead of nothing at all until the run ends.

Configuration comes from the environment:
  ANSIBLE_MCP_LOG_DIR  (optional) log directory, default <root>/logs
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# Runs kept in the log directory; older ones are dropped as new runs start.
KEEP_LOGS = 50


class RunResult(NamedTuple):
    output: str
    returncode: int
    log_path: Path
    timed_out: bool


def _slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_")[:60] or "run"


def log_dir(root: Path) -> Path:
    directory = Path(os.environ.get("ANSIBLE_MCP_LOG_DIR") or root / "logs")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _prune(directory: Path) -> None:
    for stale in sorted(directory.glob("20*.log"), reverse=True)[KEEP_LOGS:]:
        try:
            stale.unlink()
        except OSError:
            pass


def _point_latest_at(path: Path) -> None:
    """Repoint logs/latest.log at this run, without ever leaving it missing."""
    tmp = path.parent / ".latest.log.tmp"
    try:
        tmp.unlink(missing_ok=True)
        tmp.symlink_to(path.name)
        os.replace(tmp, path.parent / "latest.log")
    except OSError:
        pass


def run_logged(
    cmd: list[str],
    root: Path,
    label: str,
    timeout: int | None = None,
) -> RunResult:
    """Run cmd, tee its output to a per-run log file, and return the result.

    The output is written line by line as it arrives, so the log file is
    readable while the playbook is still running.
    """
    directory = log_dir(root)
    _prune(directory)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    path = directory / f"{stamp}-{_slug(label)}.log"
    # Two runs of the same thing within one second must not share a log file.
    attempt = 1
    while path.exists():
        attempt += 1
        path = directory / f"{stamp}-{_slug(label)}.{attempt}.log"

    chunks: list[str] = []
    killed = threading.Event()
    timer: threading.Timer | None = None

    with path.open("w", encoding="utf-8", errors="replace") as log:
        log.write(f"$ {shlex.join(cmd)}\n\n")
        log.flush()
        _point_latest_at(path)

        proc = subprocess.Popen(
            cmd,
            cwd=str(root),
            # Ansible leaves flushing to the system (see Display.display), so
            # over a pipe its output would only reach us in blocks: unbuffer it.
            env=dict(os.environ, PYTHONUNBUFFERED="1"),
            # The MCP server's own stdin is the JSON-RPC stream: never hand it
            # to a playbook that decides to prompt.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        )

        if timeout:
            def _kill() -> None:
                killed.set()
                proc.kill()

            timer = threading.Timer(timeout, _kill)
            timer.start()

        try:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                chunks.append(line)
            returncode = proc.wait()
        finally:
            if timer:
                timer.cancel()
            proc.stdout.close()

        timed_out = killed.is_set()
        note = f" (timed out after {timeout}s)" if timed_out else ""
        log.write(f"\n--- exit code {returncode}{note} ---\n")

    return RunResult("".join(chunks), returncode, path, timed_out)
