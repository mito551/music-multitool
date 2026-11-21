"""Runs the worker process: one job in flight, cancel = kill, crash = Failed event, restart on next submit."""
from __future__ import annotations

import subprocess
import threading
from collections import deque
from typing import Callable

from .protocol import Done, Event, Failed, Job, decode_event, encode_job


class Supervisor:
    def __init__(self, worker_cmd: list[str], on_event: Callable[[Event], None], env: dict | None = None):
        self._cmd = worker_cmd
        self._env = env  # None: inherit; applies from the next worker start
        self._on_event = on_event  # called from a reader thread, never with the lock held
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._job_id: str | None = None
        self._stderr: deque[str] = deque(maxlen=20)

    def set_launch(self, cmd: list[str], env: dict | None) -> None:
        self._cmd, self._env = cmd, env

    @property
    def busy(self) -> bool:
        return self._job_id is not None

    def submit(self, job: Job) -> None:
        with self._lock:
            if self._job_id is not None:
                raise RuntimeError("a job is already running")
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            self._job_id = job.id
            try:
                self._proc.stdin.write(encode_job(job) + "\n")
                self._proc.stdin.flush()
            except OSError:
                pass  # worker already gone; the reader thread reports it

    def cancel(self) -> None:
        with self._lock:
            jid, proc = self._job_id, self._proc
            self._job_id, self._proc = None, None
        if proc is not None:
            proc.kill()
        if jid is not None:
            self._on_event(Failed(jid, "cancelled"))

    def close(self) -> None:
        with self._lock:
            proc, self._proc, self._job_id = self._proc, None, None
        if proc is not None:
            proc.kill()

    def _start(self) -> None:
        proc = subprocess.Popen(self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, bufsize=1, env=self._env)
        self._proc = proc
        err = threading.Thread(target=self._read_stderr, args=(proc,), daemon=True)
        err.start()
        threading.Thread(target=self._read_stdout, args=(proc, err), daemon=True).start()

    def _read_stderr(self, proc: subprocess.Popen) -> None:
        for line in proc.stderr:
            self._stderr.append(line.rstrip())

    def _read_stdout(self, proc: subprocess.Popen, err: threading.Thread) -> None:
        for line in proc.stdout:
            try:
                ev = decode_event(line)
            except Exception:  # not an event line (stray output): ignore it, keep reading
                continue
            if isinstance(ev, (Done, Failed)):
                with self._lock:
                    if ev.id == self._job_id:
                        self._job_id = None
            self._on_event(ev)
        proc.wait()
        err.join(timeout=1)
        with self._lock:
            if self._proc is not proc:  # cancelled or closed: already reported
                return
            jid, self._proc, self._job_id = self._job_id, None, None
        if jid is not None:
            last = self._stderr[-1] if self._stderr else "no output"
            self._on_event(Failed(jid, f"worker exited: {last}"))
