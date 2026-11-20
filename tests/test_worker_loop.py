import subprocess
import sys

from audiotoolkit.core.protocol import Failed, Job, decode_event, encode_job


def start():
    return subprocess.Popen([sys.executable, "-m", "audiotoolkit.worker"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)


def send(p, line):
    p.stdin.write(line + "\n")
    p.stdin.flush()
    return decode_event(p.stdout.readline())


def test_unknown_kind_fails_and_loop_survives():
    p = start()
    try:
        ev = send(p, encode_job(Job("a", "nope", "/x", {}, "/o")))
        assert isinstance(ev, Failed) and ev.id == "a" and "unknown kind" in ev.message
        ev = send(p, encode_job(Job("b", "nope", "/x", {}, "/o")))
        assert isinstance(ev, Failed) and ev.id == "b"
    finally:
        p.kill()


def test_garbage_line_fails_with_empty_id():
    p = start()
    try:
        ev = send(p, "this is not json")
        assert isinstance(ev, Failed) and ev.id == ""
        assert p.poll() is None
    finally:
        p.kill()
