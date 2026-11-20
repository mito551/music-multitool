import sys
import threading
import time
from pathlib import Path

import pytest

from audiotoolkit.core.protocol import Done, Failed, Job
from audiotoolkit.core.supervisor import Supervisor

FAKE = [sys.executable, str(Path(__file__).parent / "fake_worker.py")]


class Collector:
    def __init__(self):
        self.events = []
        self._cv = threading.Condition()

    def __call__(self, ev):
        with self._cv:
            self.events.append(ev)
            self._cv.notify_all()

    def wait(self, n, timeout=10):
        with self._cv:
            assert self._cv.wait_for(lambda: len(self.events) >= n, timeout), self.events
        return self.events[n - 1]


def job(i, inp="ok"):
    return Job(i, "noop", inp, {}, "/tmp/out")


def test_submit_emits_done():
    c = Collector()
    sup = Supervisor(FAKE, c)
    sup.submit(job("a"))
    assert isinstance(c.wait(1), Done)
    assert not sup.busy
    sup.close()


def test_crash_midjob_emits_failed_then_restarts():
    c = Collector()
    sup = Supervisor(FAKE, c)
    sup.submit(job("a", "crash"))
    ev = c.wait(1)
    assert isinstance(ev, Failed) and ev.id == "a" and "worker exited" in ev.message and "out of memory" in ev.message
    sup.submit(job("b"))
    assert isinstance(c.wait(2), Done)
    sup.close()


def test_cancel_kills_and_emits_cancelled():
    c = Collector()
    sup = Supervisor(FAKE, c)
    sup.submit(job("a", "sleep"))
    time.sleep(0.3)
    sup.cancel()
    ev = c.wait(1)
    assert ev == Failed("a", "cancelled")
    assert not sup.busy
    sup.submit(job("b"))
    assert isinstance(c.wait(2), Done)
    sup.close()


def test_submit_while_busy_raises():
    sup = Supervisor(FAKE, Collector())
    sup.submit(job("a", "sleep"))
    with pytest.raises(RuntimeError):
        sup.submit(job("b"))
    sup.cancel()
    sup.close()


def test_non_event_json_line_does_not_kill_reader():
    c = Collector()
    sup = Supervisor(FAKE, c)
    sup.submit(job("a", "garbage"))
    assert isinstance(c.wait(1), Done)
    sup.close()
