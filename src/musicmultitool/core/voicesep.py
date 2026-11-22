"""Polyphonic MIDI voice separation: split a MIDI file's notes into N melodic lines.

Deterministic core of the spec (cost-based beam search over onset slices). Pure Python plus `mido`.
Implemented cost terms: pitch distance, repeat bonus, gap, overlap, range, tessitura, melody/bass role, source track,
dynamics, voice overlap between neighbours. Not implemented yet (see the spec): contour, rhythm, pins, refinement pass,
per-note confidence, learned model costs, FREE (unordered) voices.
"""
from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass, field
from itertools import combinations

import mido

# spec section 4.2 presets: label -> soft range (MIDI pitch)
RANGES = {"soprano": (60, 79), "alto": (55, 74), "tenor": (48, 67), "bass": (40, 62)}
DRUM_CHANNEL = 9


@dataclass(frozen=True)
class Note:
    id: int
    pitch: int
    on: int  # ticks
    off: int
    vel: int
    track: int
    channel: int


@dataclass(frozen=True)
class Voice:
    label: str
    role: str = "INNER"  # MELODY | BASS | INNER
    lo: int | None = None
    hi: int | None = None


@dataclass
class Params:
    beam: int = 64
    tau_on: float = 0.040  # seconds; onsets this close form one slice in PERFORMANCE mode
    delta_ov: float = 0.080  # seconds of overlap treated as legato
    w_pitch: float = 1.0
    w_gap: float = 2.0
    w_ovl_base: float = 50.0
    w_ovl: float = 20.0
    w_range: float = 2.0
    w_cent: float = 0.3
    w_role: float = 3.0
    w_src: float = 0.5
    w_dyn: float = 1.0
    w_vov: float = 1.5
    mode: str = "auto"  # auto | quantized | performance


@dataclass
class Midi:
    notes: list[Note]
    tpq: int
    meta: list[tuple[int, mido.MetaMessage]]  # (abs tick, message): tempo, time signature, key
    tempos: list[tuple[int, int]]  # (abs tick, microseconds per quarter)
    dropped: list[dict] = field(default_factory=list)

    def seconds(self, tick: int) -> float:
        """Tick to seconds through the tempo map."""
        t, tempo, sec = 0, 500000, 0.0
        for at, new in self.tempos:
            if at >= tick:
                break
            sec += (at - t) * tempo / 1e6 / self.tpq
            t, tempo = at, new
        return sec + (tick - t) * tempo / 1e6 / self.tpq

    def ticks(self, seconds: float) -> int:
        """Seconds to ticks at the first tempo, for tolerances (good enough: tempo changes are rare)."""
        tempo = self.tempos[0][1] if self.tempos else 500000
        return max(0, round(seconds * 1e6 / tempo * self.tpq))


def read_midi(path: str) -> Midi:
    mid = mido.MidiFile(path)
    notes: list[Note] = []
    meta: list[tuple[int, mido.MetaMessage]] = []
    tempos: list[tuple[int, int]] = []
    pending: dict[tuple[int, int], list[tuple[int, int]]] = {}  # (channel, pitch) -> FIFO of (on tick, vel)
    raw: list[tuple[int, int, int, int, int, int]] = []  # on, off, pitch, vel, track, channel
    for ti, track in enumerate(mid.tracks):
        tick = 0
        pending.clear()
        for msg in track:
            tick += msg.time
            if msg.is_meta:
                if msg.type == "set_tempo":
                    tempos.append((tick, msg.tempo))
                if msg.type in ("set_tempo", "time_signature", "key_signature"):
                    meta.append((tick, msg))
            elif msg.type == "note_on" and msg.velocity > 0:
                pending.setdefault((msg.channel, msg.note), []).append((tick, msg.velocity))
            elif msg.type in ("note_off", "note_on"):
                fifo = pending.get((msg.channel, msg.note))
                if fifo:
                    on, vel = fifo.pop(0)
                    raw.append((on, tick, msg.note, vel, ti, msg.channel))
    tempos.sort()
    out = Midi([], mid.ticks_per_beat, sorted(meta, key=lambda m: m[0]), tempos)
    raw.sort()
    for on, off, pitch, vel, ti, ch in raw:
        if ch == DRUM_CHANNEL:
            out.dropped.append({"pitch": pitch, "tick": on, "why": "percussion"})
        elif out.seconds(off) - out.seconds(on) < 0.010:
            out.dropped.append({"pitch": pitch, "tick": on, "why": "shorter than 10 ms"})
        else:
            out.notes.append(Note(len(out.notes), pitch, on, off, vel, ti, ch))
    return out


def grid_conformity(m: Midi) -> float:
    """Fraction of onsets within 1/128 note of a 16th-note grid (spec 5.4, with a stricter grid than 1/32)."""
    if not m.notes:
        return 1.0
    step, tol = m.tpq / 4, m.tpq / 32
    ok = sum(1 for n in m.notes if min(n.on % step, step - n.on % step) <= tol)
    return ok / len(m.notes)


def make_slices(m: Midi, quantized: bool, p: Params) -> list[list[Note]]:
    notes = sorted(m.notes, key=lambda n: (n.on, -n.pitch))
    slices: list[list[Note]] = []
    tol = 0 if quantized else m.ticks(p.tau_on)
    last = None
    for n in notes:
        # ponytail: fixed tau_on, spec wants min(40 ms, 0.15 x local IOI); and no rolled-chord merging
        if slices and last is not None and n.on - last <= tol:
            slices[-1].append(n)
        else:
            slices.append([n])
        last = n.on
    return [sorted(s, key=lambda n: -n.pitch) for s in slices]


def _f(d: int) -> float:
    return -0.5 if d == 0 else (d if d <= 12 else 12 + 2 * (d - 12))


class _Cost:
    def __init__(self, m: Midi, voices: list[Voice], p: Params):
        self.m, self.v, self.p = m, voices, p
        self.dov = m.ticks(p.delta_ov)

    def note(self, n: Note, vi: int, top: Note, bottom: Note) -> float:
        v, p = self.v[vi], self.p
        c = 0.0
        if v.lo is not None and n.pitch < v.lo - 3:
            c += p.w_range * (v.lo - 3 - n.pitch)
        if v.hi is not None and n.pitch > v.hi + 3:
            c += p.w_range * (n.pitch - v.hi - 3)
        if v.lo is not None and v.hi is not None:
            c += p.w_cent * abs(n.pitch - (v.lo + v.hi) / 2) / 12
        if v.role == "MELODY" and n is not top:
            c += p.w_role
        if v.role == "BASS" and n is not bottom:
            c += p.w_role
        return c

    def link(self, a: Note | None, b: Note) -> float:
        if a is None:
            return 0.0
        p = self.p
        c = p.w_pitch * _f(abs(b.pitch - a.pitch))
        gap = b.on - a.off
        if gap < 0:
            over = -gap
            if over > self.dov:
                c += p.w_ovl_base + p.w_ovl * over / self.m.tpq
        else:
            c += p.w_gap * min(math.log2(1 + gap / self.m.tpq), 3)
        c += p.w_src * (a.track != b.track) + p.w_dyn * abs(a.vel - b.vel) / 127
        return c

    def neighbours(self, front: tuple, vi: int, n: Note) -> float:
        """Voice overlap: n must not pass the previous pitch of the voice above (higher) or below."""
        c = 0.0
        if vi > 0 and front[vi - 1] is not None and n.pitch > front[vi - 1].pitch:
            c += self.p.w_vov * (n.pitch - front[vi - 1].pitch)
        if vi + 1 < len(front) and front[vi + 1] is not None and n.pitch < front[vi + 1].pitch:
            c += self.p.w_vov * (front[vi + 1].pitch - n.pitch)
        return c


def _spread(k: int, n: int) -> list[int]:
    """Indices of n notes out of k, always keeping the highest and lowest."""
    return [round(i * (k - 1) / (n - 1)) for i in range(n)] if n > 1 else [0]


def separate(m: Midi, voices: list[Voice], p: Params | None = None) -> tuple[dict[int, int], dict]:
    """Returns ({note id: voice index}, report). Every note ends up in exactly one voice."""
    p = p or Params()
    N = len(voices)
    if N < 1:
        raise ValueError("need at least one voice")
    conf = grid_conformity(m)
    quantized = {"quantized": True, "performance": False}.get(p.mode, conf >= 0.98)
    cost = _Cost(m, voices, p)
    slices = make_slices(m, quantized, p)
    # beam state: (cost, back-pointer chain, frontier = last note per voice)
    beam: list[tuple[float, tuple | None, tuple]] = [(0.0, None, (None,) * N)]
    for sl in slices:
        top, bottom = sl[0], sl[-1]
        main = [sl[i] for i in _spread(len(sl), min(len(sl), N))]  # surplus notes are attached below (soft overlap)
        nxt: dict[tuple, tuple[float, tuple | None, tuple]] = {}
        for c0, back, front in beam:
            for chosen in combinations(range(N), len(main)):
                c, new = c0, list(front)
                for n, vi in zip(main, chosen):
                    c += cost.note(n, vi, top, bottom) + cost.link(front[vi], n) + cost.neighbours(front, vi, n)
                    new[vi] = n
                key = tuple(x.id if x else -1 for x in new)
                if key not in nxt or c < nxt[key][0]:
                    nxt[key] = (c, (back, tuple((n.id, vi) for n, vi in zip(main, chosen))), tuple(new))
        beam = sorted(nxt.values(), key=lambda s: s[0])[: p.beam]
    total, chain, _ = min(beam, key=lambda s: s[0])
    assignment: dict[int, int] = {}
    while chain:
        chain, assign = chain
        assignment.update(assign)
    # extras: attach each to the voice whose neighbouring assigned note links cheapest
    by_voice: dict[int, list[Note]] = {i: [] for i in range(N)}
    for n in m.notes:
        if n.id in assignment:
            by_voice[assignment[n.id]].append(n)
    for notes in by_voice.values():
        notes.sort(key=lambda n: n.on)
    overflow_events = []
    for n in m.notes:
        if n.id in assignment:
            continue
        best_v, best_c = 0, math.inf
        for vi, notes in by_voice.items():
            i = bisect.bisect([x.on for x in notes], n.on)
            prev = notes[i - 1] if i else None
            c = cost.link(prev, n) + cost.note(n, vi, n, n)
            if c < best_c:
                best_v, best_c = vi, c
        assignment[n.id] = best_v
        overflow_events.append({"note": n.id, "tick": n.on, "voice": best_v})
    report = {
        "mode": "QUANTIZED" if quantized else "PERFORMANCE",
        "grid_conformity": round(conf, 4),
        "voices": [{"index": i, "label": v.label, "note_count": sum(1 for x in assignment.values() if x == i)}
                   for i, v in enumerate(voices)],
        "overflow_events": overflow_events,
        "dropped": m.dropped,
        "total_cost": round(total, 3),
        "model": None,
    }
    return assignment, report


def default_voices(n: int) -> list[Voice]:
    """Spec 4.2: top = MELODY, bottom = BASS, the rest INNER; SATB presets for four."""
    if n == 4:
        return [Voice(k.capitalize(), r, *RANGES[k]) for k, r in zip(RANGES, ("MELODY", "INNER", "INNER", "BASS"))]
    return [Voice(f"voice-{i + 1}", "MELODY" if i == 0 else "BASS" if i == n - 1 and n > 1 else "INNER") for i in range(n)]


def write_midi(m: Midi, voices: list[Voice], assignment: dict[int, int], path: str) -> None:
    out = mido.MidiFile(type=1, ticks_per_beat=m.tpq)
    head = mido.MidiTrack()
    head.append(mido.MetaMessage("track_name", name="tempo", time=0))
    last = 0
    for tick, msg in m.meta:
        head.append(msg.copy(time=tick - last))
        last = tick
    out.tracks.append(head)
    channels = [c for c in range(16) if c != DRUM_CHANNEL]
    for vi, v in enumerate(voices):
        ch = channels[vi % len(channels)]
        events = []  # (tick, order, message): offs sort before ons at the same tick
        for n in m.notes:
            if assignment.get(n.id) == vi:
                events.append((n.on, 1, mido.Message("note_on", channel=ch, note=n.pitch, velocity=n.vel)))
                events.append((n.off, 0, mido.Message("note_off", channel=ch, note=n.pitch, velocity=0)))
        events.sort(key=lambda e: (e[0], e[1]))
        track = mido.MidiTrack([mido.MetaMessage("track_name", name=v.label, time=0)])
        last = 0
        for tick, _, msg in events:
            track.append(msg.copy(time=tick - last))
            last = tick
        out.tracks.append(track)
    out.save(path)


def write_report(report: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(report, f, indent=1)
