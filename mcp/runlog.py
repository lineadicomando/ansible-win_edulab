# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-run log files for the MCP Ansible runners.

Each run streams its output to <root>/logs/<timestamp>-<label>.log while it is
still running, and repoints <root>/logs/latest.log at it, so that a
`tail -F logs/latest.log` left open in a terminal shows what the MCP tools are
doing instead of nothing at all until the run ends.

`run_logged_async` additionally turns that same stream into MCP progress
notifications, so a client that renders them shows the current task while the
playbook runs rather than only its result at the end.

Configuration comes from the environment:
  ANSIBLE_MCP_LOG_DIR  (optional) log directory, default <root>/logs
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import subprocess
import threading
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

# Runs kept in the log directory; older ones are dropped as new runs start.
KEEP_LOGS = 50

# Seconds between progress notifications. Ansible emits a line per host per
# task, which on a full lab is far more than a progress bar can use: lines are
# folded into one message per interval instead.
PROGRESS_INTERVAL = 1.0

NotifyFn = Callable[[int, str], Coroutine[Any, Any, None]]


class RunResult(NamedTuple):
    output: str
    returncode: int
    log_path: Path
    timed_out: bool


def _redactor(redact: list[str] | None) -> Callable[[str], str]:
    """Replace known secret values wherever they appear on their way out."""
    values = sorted((value for value in (redact or []) if value), key=len, reverse=True)
    if not values:
        return lambda text: text

    def hide(text: str) -> str:
        for value in values:
            text = text.replace(value, "********")
        return text

    return hide


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


# "TASK [role : name] ******" and "ok: [PC01]" / "fatal: [PC28]: UNREACHABLE!".
_TASK_RE = re.compile(r"^(?:TASK|HANDLER) \[(?P<name>.+?)\] \*+\s*$")
_HOST_RE = re.compile(
    r"^(?P<status>ok|changed|failed|fatal|skipping|unreachable): \[(?P<host>[^ \]]+)"
)
_BAD_STATUS = {"failed", "fatal", "unreachable"}


class ProgressSummary:
    """Folds ansible-playbook output lines into one-line progress messages.

    Returns None for lines that say nothing new, so callers can ignore the
    banners, the included-file lines and the per-host recap table.
    """

    def __init__(self) -> None:
        self.task: str | None = None
        self.hosts = 0
        self.failed = 0

    def feed(self, line: str) -> str | None:
        line = line.rstrip("\n")

        task = _TASK_RE.match(line)
        if task:
            # "role_name : Human task name" reads better as just the task name.
            self.task = task.group("name").split(" : ")[-1]
            self.hosts = 0
            self.failed = 0
            return self.task

        host = _HOST_RE.match(line)
        if host:
            self.hosts += 1
            if host.group("status") in _BAD_STATUS:
                self.failed += 1
            return self._message(host.group("host"))

        if line.startswith("PLAY RECAP"):
            self.task = None
            return "PLAY RECAP"

        return None

    def _message(self, host: str) -> str:
        detail = f"{self.hosts} host" + (f", {self.failed} failed" if self.failed else "")
        return f"{self.task} — {host} ({detail})" if self.task else f"{host} ({detail})"


def new_log_path(root: Path, label: str) -> Path:
    """Reserve the log file for a run that is about to start."""
    directory = log_dir(root)
    _prune(directory)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    path = directory / f"{stamp}-{_slug(label)}.log"
    # Two runs of the same thing within one second must not share a log file.
    attempt = 1
    while path.exists():
        attempt += 1
        path = directory / f"{stamp}-{_slug(label)}.{attempt}.log"
    # Claim the name now: a background run hands it out before writing to it.
    path.touch()
    return path


def run_logged(
    cmd: list[str],
    root: Path,
    label: str,
    timeout: int | None = None,
    on_line: Callable[[str], None] | None = None,
    path: Path | None = None,
    env: dict[str, str] | None = None,
    redact: list[str] | None = None,
) -> RunResult:
    """Run cmd, tee its output to a per-run log file, and return the result.

    The output is written line by line as it arrives, so the log file is
    readable while the playbook is still running. Each line is also handed to
    on_line, if given, from this thread.
    """
    if path is None:
        path = new_log_path(root, label)

    hide = _redactor(redact)
    chunks: list[str] = []
    killed = threading.Event()
    timer: threading.Timer | None = None

    with path.open("w", encoding="utf-8", errors="replace") as log:
        # The command line goes in the log so a run can be reproduced by hand;
        # a secret passed on it must not go with it.
        log.write(f"$ {hide(shlex.join(cmd))}\n\n")
        log.flush()
        _point_latest_at(path)

        proc: subprocess.Popen[str] | None = None
        returncode = -1
        try:
            # Inside the try: a command that cannot even start must still
            # terminate its own log, or it reads as running forever.
            proc = subprocess.Popen(
                cmd,
                cwd=str(root),
                # Ansible leaves flushing to the system (see Display.display),
                # so over a pipe its output would only reach us in blocks:
                # unbuffer it.
                env=dict(os.environ, PYTHONUNBUFFERED="1", **(env or {})),
                # The MCP server's own stdin is the JSON-RPC stream: never hand
                # it to a playbook that decides to prompt.
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

            for line in proc.stdout:
                line = hide(line)
                log.write(line)
                log.flush()
                chunks.append(line)
                if on_line is not None:
                    on_line(line)
            returncode = proc.wait()
        except Exception as exc:
            log.write(f"\n[runner error] {exc!r}\n")
            raise
        finally:
            if timer:
                timer.cancel()
            if proc is not None and proc.stdout is not None:
                proc.stdout.close()
            # Always leave the marker behind, even on the way out of an
            # exception: an unterminated log reads as a run still going.
            timed_out = killed.is_set()
            note = f" (timed out after {timeout}s)" if timed_out else ""
            log.write(f"\n--- exit code {returncode}{note} ---\n")

    return RunResult("".join(chunks), returncode, path, timed_out)


async def _pump(queue: asyncio.Queue[str | None], notify: NotifyFn) -> None:
    """Turn queued output lines into at most one notification per interval."""
    summary = ProgressSummary()
    loop = asyncio.get_running_loop()
    sent = 0
    pending: str | None = None
    last = 0.0

    while True:
        try:
            # The timeout doubles as a tick, so the last line of a quiet
            # stretch still gets sent instead of waiting for the next one.
            line = await asyncio.wait_for(queue.get(), timeout=PROGRESS_INTERVAL)
        except TimeoutError:
            line = ""
        if line is None:
            break
        if line:
            message = summary.feed(line)
            if message:
                pending = message
        now = loop.time()
        if pending and now - last >= PROGRESS_INTERVAL:
            sent += 1
            if not await _notify(notify, sent, pending):
                return
            pending, last = None, now

    if pending:
        await _notify(notify, sent + 1, pending)


async def _notify(notify: NotifyFn, progress: int, message: str) -> bool:
    """Send one progress notification. False means: stop trying.

    A client that asked for progress but cannot take it must not be able to
    fail the run it asked about.
    """
    try:
        await notify(progress, message)
    except Exception:
        logger.debug("progress notification failed; giving up", exc_info=True)
        return False
    return True


async def run_logged_async(
    cmd: list[str],
    root: Path,
    label: str,
    notify: NotifyFn | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    redact: list[str] | None = None,
) -> RunResult:
    """run_logged in a worker thread, reporting progress through notify."""
    if notify is None:
        return await asyncio.to_thread(
            run_logged, cmd, root, label, timeout, env=env, redact=redact
        )

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def on_line(line: str) -> None:
        # Called from the reader thread: hand the line to the loop, don't touch
        # the queue directly.
        loop.call_soon_threadsafe(queue.put_nowait, line)

    pump = asyncio.create_task(_pump(queue, notify))
    try:
        return await asyncio.to_thread(
            run_logged, cmd, root, label, timeout, on_line, env=env, redact=redact
        )
    finally:
        queue.put_nowait(None)
        await pump


# The marker run_logged leaves behind; its absence is what "still running" means.
_DONE_RE = re.compile(r"^--- exit code (?P<code>-?\d+)(?P<note>[^-]*)---\s*$")


class RunStatus(NamedTuple):
    run: str
    running: bool
    exit_code: int | None
    note: str
    lines: list[str]
    next_line: int
    total_lines: int


def start_logged(
    cmd: list[str],
    root: Path,
    label: str,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    redact: list[str] | None = None,
) -> Path:
    """Start cmd in the background and return its log path straight away.

    The caller polls the log through read_log instead of waiting. The worker is
    a daemon thread: if the MCP server goes away, so does the run it was
    watching, exactly as a foreground run would.
    """
    path = new_log_path(root, label)

    def work() -> None:
        try:
            run_logged(cmd, root, label, timeout, path=path, env=env, redact=redact)
        except Exception:
            logger.exception("background run failed: %s", path.name)

    threading.Thread(target=work, name=f"run:{path.stem}", daemon=True).start()
    return path


def resolve_run(root: Path, run: str) -> Path:
    """Map a run name to its log file, refusing anything outside the log dir."""
    directory = log_dir(root)
    name = Path(run or "latest").name  # never let a run name walk the tree
    if not name.endswith(".log"):
        name += ".log"
    path = directory / name
    if not path.exists():
        raise FileNotFoundError(f"No run named {name!r} in {directory}")
    return path


def read_log(root: Path, run: str = "latest", since_line: int = 0, max_lines: int = 200) -> RunStatus:
    """Read a run's log from since_line, and say whether it is still going."""
    path = resolve_run(root, run)
    text = path.read_text(encoding="utf-8", errors="replace")
    all_lines = text.splitlines()

    running, exit_code, note = True, None, ""
    for line in reversed(all_lines[-3:]):
        done = _DONE_RE.match(line)
        if done:
            running = False
            exit_code = int(done.group("code"))
            note = done.group("note").strip()
            break

    start = max(0, since_line)
    lines = all_lines[start : start + max_lines]
    # resolve_run followed the symlink for "latest": report the real run name.
    return RunStatus(
        run=path.resolve().name,
        running=running,
        exit_code=exit_code,
        note=note,
        lines=lines,
        next_line=start + len(lines),
        total_lines=len(all_lines),
    )


def format_status(status: RunStatus, tool: str = "run_status") -> str:
    """Render a RunStatus for an MCP tool result."""
    if status.running:
        state = "running"
    else:
        state = f"finished (exit code {status.exit_code})"
        if status.note:
            state += f" {status.note}"

    shown = f"lines {status.next_line - len(status.lines) + 1}-{status.next_line}" if status.lines else "no new lines"
    header = f"run: {status.run}\nstatus: {state}\n{shown} of {status.total_lines}"
    body = "\n".join(status.lines)

    remaining = status.total_lines - status.next_line
    if remaining > 0:
        footer = f"[{remaining} more lines] {tool}(run=\"{status.run}\", since_line={status.next_line})"
    elif status.running:
        footer = f"[still running] {tool}(run=\"{status.run}\", since_line={status.next_line})"
    else:
        footer = "[end of run]"

    return "\n\n".join(part for part in (header, body, footer) if part)
