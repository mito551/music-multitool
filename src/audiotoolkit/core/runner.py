"""Drives the queue: one job in flight, skip-existing via manifests, chain expansion, cancel."""
from __future__ import annotations

from typing import Callable

from .outputs import load_manifest, song_dir
from .presets import Preset, Step, select_inputs
from .protocol import Done, Event, Failed, Job, Output, Progress
from .queue import BatchQueue, Item, Status


class BatchRunner:
    def __init__(self, queue: BatchQueue, submit: Callable[[Job], None], cancel_worker: Callable[[], None],
                 out_root: str, presets: dict[str, Preset], skip_existing: bool = True,
                 on_change: Callable[[Item], None] = lambda item: None):
        self.queue, self._submit, self._cancel_worker = queue, submit, cancel_worker
        self.out_root, self.presets, self.skip_existing, self._on_change = out_root, presets, skip_existing, on_change
        self.running = False
        self._reset_item()

    def _reset_item(self) -> None:
        self._cur: Item | None = None
        self._steps: list[Step] = []
        self._step_idx = -1
        self._jobs: list[Job] = []
        self._step_total = self._step_done = self._counter = 0
        self._collected: list[Output] = []
        self._ran_any = False
        self._inflight: Job | None = None

    # -- public -------------------------------------------------------------------------------------------------

    def start(self) -> None:
        if not self.running:
            self.running = True
            self._pump()

    def cancel(self) -> None:
        if not self.running:
            return
        item = self._cur
        self._inflight = None  # so the supervisor's "cancelled" event is ignored
        self.running = False
        self._reset_item()
        self._cancel_worker()
        if item is not None:
            self._mark(item, Status.CANCELLED)

    def on_event(self, ev: Event) -> None:
        if self._inflight is None or ev.id != self._inflight.id or self._cur is None:
            return
        item = self._cur
        if isinstance(ev, Progress):
            item.fraction = None if ev.fraction is None else self._overall(ev.fraction)
            item.message = ev.note
            self._on_change(item)
        elif isinstance(ev, Done):
            self._inflight = None
            self._collected += ev.outputs
            item.result = ev.result
            self._step_done += 1
            self._pump()
        elif isinstance(ev, Failed):
            self._inflight = None
            self._finish(Status.FAILED, ev.message)
            self._pump()

    # -- internals ----------------------------------------------------------------------------------------------

    def _mark(self, item: Item, status: Status, message: str = "") -> None:
        self.queue.mark(item.id, status, fraction=item.fraction if status is Status.RUNNING else None, message=message)
        self._on_change(item)

    def _overall(self, job_fraction: float) -> float:
        return (self._step_idx + (self._step_done + job_fraction) / max(self._step_total, 1)) / len(self._steps)

    def _finish(self, status: Status, message: str = "") -> None:
        item = self._cur
        item.outputs = list(self._collected)
        self._mark(item, status, message)
        self._reset_item()

    def _begin(self, item: Item) -> None:
        self._cur = item
        if item.kind == "chain":
            preset = self.presets.get(item.opts.get("preset", ""))
            if preset is None:
                self._mark(item, Status.FAILED, f"unknown preset: {item.opts.get('preset')}")
                self._reset_item()
                return
            self._steps = list(preset.steps)
        else:
            self._steps = [Step(item.kind, self.queue.effective_opts(item))]
        self._mark(item, Status.RUNNING)

    def _plan_step(self) -> bool:
        step = self._steps[self._step_idx]
        item = self._cur
        inputs = select_inputs(step, item.source, self._collected)
        if not inputs:
            self._finish(Status.FAILED, f"step {self._step_idx + 1}: no input matches '{step.input}'")
            return False
        out_dir = song_dir(self.out_root, item.song)
        self._jobs = []
        for path in inputs:
            self._counter += 1
            self._jobs.append(Job(f"{item.id}.{self._counter}", step.kind, path, dict(step.opts), out_dir))
        self._step_total, self._step_done = len(self._jobs), 0
        return True

    def _pump(self) -> None:
        """Advance until a job is in flight or the queue is empty."""
        while True:
            if self._cur is None:
                item = self.queue.next_pending()
                if item is None:
                    self.running = False
                    return
                self._begin(item)
                continue
            if self._jobs:
                job = self._jobs.pop(0)
                outs = load_manifest(job) if self.skip_existing else None
                if outs is not None:
                    self._collected += outs
                    self._step_done += 1
                    continue
                self._ran_any = True
                self._inflight = job
                self._submit(job)
                return
            self._step_idx += 1
            if self._step_idx >= len(self._steps):
                self._finish(Status.DONE if self._ran_any else Status.SKIPPED)
            else:
                self._plan_step()
