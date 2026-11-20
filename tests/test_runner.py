from audiotoolkit.core.outputs import song_dir, write_manifest
from audiotoolkit.core.presets import Preset, Step
from audiotoolkit.core.protocol import Done, Failed, Job, Output, Progress
from audiotoolkit.core.queue import BatchQueue, Status
from audiotoolkit.core.runner import BatchRunner

STEMS_TO_MIDI = Preset("Stems→MIDI", (Step("separate"), Step("midi", {}, "stem:*")))


class Harness:
    def __init__(self, tmp_path, presets=None, skip=True):
        self.out = str(tmp_path / "out")
        self.tmp = tmp_path
        self.jobs: list[Job] = []
        self.cancelled = 0
        self.q = BatchQueue()
        self.runner = BatchRunner(self.q, self.jobs.append, self._cancel, self.out, presets or {}, skip)

    def _cancel(self):
        self.cancelled += 1

    def src(self, name):
        p = self.tmp / name
        p.write_bytes(b"x")
        return str(p)

    def finish(self, outputs=(), result=None):
        """Complete the last submitted job the way the worker would: files, manifest, Done event."""
        job = self.jobs[-1]
        outs = []
        for role, path in outputs:
            with open(path, "w") as f:
                f.write("x")
            outs.append(Output(role, path))
        write_manifest(job, outs)
        self.runner.on_event(Done(job.id, tuple(outs), result or {}))

    def stems(self, *names):
        d = self.tmp / "stems"
        d.mkdir(exist_ok=True)
        return [(f"stem:{n}", str(d / f"{n}.wav")) for n in names]


def test_items_run_sequentially(tmp_path):
    h = Harness(tmp_path)
    a, b = h.q.add([h.src("a.mp3"), h.src("b.mp3")], "midi", {})
    h.runner.start()
    assert [j.input for j in h.jobs] == [a.source] and a.status is Status.RUNNING and h.runner.running
    h.finish([("midi", str(tmp_path / "a.mid"))])
    assert a.status is Status.DONE and [j.input for j in h.jobs] == [a.source, b.source]
    h.finish([("midi", str(tmp_path / "b.mid"))])
    assert b.status is Status.DONE and not h.runner.running


def test_progress_updates_item(tmp_path):
    h = Harness(tmp_path)
    (a,) = h.q.add([h.src("a.mp3")], "separate", {})
    h.runner.start()
    h.runner.on_event(Progress(h.jobs[0].id, 0.4, "separating"))
    assert a.fraction == 0.4 and a.message == "separating"


def prewritten_manifest(h, item, kind):
    job = Job("x", kind, item.source, {}, song_dir(h.out, item.song))
    out = h.tmp / "done.mid"
    out.write_bytes(b"x")
    write_manifest(job, [Output("midi", str(out))])
    return [Output("midi", str(out))]


def test_skip_existing_does_not_submit(tmp_path):
    h = Harness(tmp_path)
    (a,) = h.q.add([h.src("a.mp3")], "midi", {})
    outs = prewritten_manifest(h, a, "midi")
    h.runner.start()
    assert h.jobs == [] and a.status is Status.SKIPPED and a.outputs == outs and not h.runner.running


def test_skip_disabled_resubmits(tmp_path):
    h = Harness(tmp_path, skip=False)
    (a,) = h.q.add([h.src("a.mp3")], "midi", {})
    prewritten_manifest(h, a, "midi")
    h.runner.start()
    assert len(h.jobs) == 1


def test_failed_marks_item_and_continues(tmp_path):
    h = Harness(tmp_path)
    a, b = h.q.add([h.src("a.mp3"), h.src("b.mp3")], "midi", {})
    h.runner.start()
    h.runner.on_event(Failed(h.jobs[0].id, "boom"))
    assert (a.status, a.message) == (Status.FAILED, "boom") and h.jobs[-1].input == b.source


def test_chain_fans_out_per_stem(tmp_path):
    h = Harness(tmp_path, {STEMS_TO_MIDI.name: STEMS_TO_MIDI})
    (a,) = h.q.add([h.src("a.mp3")], "chain", {"preset": STEMS_TO_MIDI.name})
    h.runner.start()
    assert h.jobs[0].kind == "separate"
    stems = h.stems("vocals", "drums")
    h.finish(stems)
    assert [(j.kind, j.input) for j in h.jobs[1:]] == [("midi", stems[0][1])]
    h.finish([("midi", str(tmp_path / "vocals.mid"))])
    assert [(j.kind, j.input) for j in h.jobs[2:]] == [("midi", stems[1][1])]
    h.finish([("midi", str(tmp_path / "drums.mid"))])
    assert a.status is Status.DONE and len(a.outputs) == 4
    assert {j.out_dir for j in h.jobs} == {song_dir(h.out, "a")}


def test_chain_empty_selection_fails_item(tmp_path):
    p = Preset("bad", (Step("convert"), Step("midi", {}, "stem:*")))
    h = Harness(tmp_path, {"bad": p})
    (a,) = h.q.add([h.src("a.mp3")], "chain", {"preset": "bad"})
    h.runner.start()
    h.finish([("audio", str(tmp_path / "a.wav"))])
    assert a.status is Status.FAILED and a.message == "step 2: no input matches 'stem:*'"


def test_chain_unknown_preset_fails_item(tmp_path):
    h = Harness(tmp_path)
    (a,) = h.q.add([h.src("a.mp3")], "chain", {"preset": "ghost"})
    h.runner.start()
    assert a.status is Status.FAILED and "ghost" in a.message and h.jobs == []


def test_cancel_marks_cancelled_and_leaves_rest_pending(tmp_path):
    h = Harness(tmp_path)
    a, b = h.q.add([h.src("a.mp3"), h.src("b.mp3")], "midi", {})
    h.runner.start()
    job_id = h.jobs[0].id
    h.runner.cancel()
    h.runner.on_event(Failed(job_id, "cancelled"))  # supervisor reports it; must be ignored
    assert h.cancelled == 1 and a.status is Status.CANCELLED and b.status is Status.PENDING
    assert len(h.jobs) == 1 and not h.runner.running


def test_rerun_after_cancel_resumes_at_unfinished_step(tmp_path):
    h = Harness(tmp_path, {STEMS_TO_MIDI.name: STEMS_TO_MIDI})
    (a,) = h.q.add([h.src("a.mp3")], "chain", {"preset": STEMS_TO_MIDI.name})
    h.runner.start()
    h.finish(h.stems("vocals", "drums"))
    assert h.jobs[-1].kind == "midi"
    h.runner.cancel()  # the midi job never wrote a manifest
    assert h.q.retry_failed() == 1
    n = len(h.jobs)
    h.runner.start()
    assert [j.kind for j in h.jobs[n:]] == ["midi"]  # separate step resumed from its manifest
    assert sum(j.kind == "separate" for j in h.jobs) == 1
