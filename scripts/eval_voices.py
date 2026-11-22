"""Score the voice separator against labelled scores from the music21 corpus.

    pip install music21 mido
    PYTHONPATH=src python scripts/eval_voices.py bach --limit 50
    PYTHONPATH=src python scripts/eval_voices.py haydn mozart beethoven --generic

Each score part is one ground-truth voice. Metrics: note accuracy under the best voice relabelling, and link
precision/recall/F1 over consecutive notes of one voice (spec section 12.1). Input to the separator carries no part labels.
"""
from __future__ import annotations

import argparse
import itertools
import statistics
import sys
import time

from music21 import corpus, converter

from musicmultitool.core.voicesep import Midi, Note, Params, Voice, default_voices, separate

TPQ = 480


def load(path: str) -> tuple[Midi, dict[int, int], int] | None:
    score = converter.parse(path).stripTies()
    notes, truth = [], {}
    for vi, part in enumerate(score.parts):
        for el in part.flatten().notes:
            for p in (el.pitches if el.isChord else [el.pitch]):
                on, dur = round(float(el.offset) * TPQ), round(float(el.quarterLength) * TPQ)
                if dur <= 0:
                    continue
                n = Note(len(notes), p.midi, on, on + dur, 64, 0, 0)  # one source track: no label leaks
                notes.append(n)
                truth[n.id] = vi
    if not notes or len(score.parts) < 2:
        return None
    return Midi(notes, TPQ, [], [(0, 500000)]), truth, len(score.parts)


def links(assign: dict[int, int], notes: list[Note]) -> set[tuple[int, int]]:
    by: dict[int, list[Note]] = {}
    for n in sorted(notes, key=lambda n: (n.on, -n.pitch)):
        by.setdefault(assign[n.id], []).append(n)
    return {(a.id, b.id) for line in by.values() for a, b in zip(line, line[1:])}


def score_piece(m: Midi, truth: dict[int, int], assign: dict[int, int], n_voices: int) -> tuple[float, float, float, float]:
    best = max(sum(1 for i, v in assign.items() if perm[v] == truth[i])
               for perm in itertools.permutations(range(n_voices))) / len(assign)
    t, p = links(truth, m.notes), links(assign, m.notes)
    tp = len(t & p)
    prec, rec = tp / max(len(p), 1), tp / max(len(t), 1)
    return best, prec, rec, 2 * prec * rec / max(prec + rec, 1e-9)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("composers", nargs="+")
    ap.add_argument("--limit", type=int, default=0, help="pieces per composer, 0 = all")
    ap.add_argument("--generic", action="store_true", help="no SATB ranges; only melody/bass roles")
    ap.add_argument("--beam", type=int, default=64)
    ap.add_argument("--max-parts", type=int, default=6)
    a = ap.parse_args()
    for comp in a.composers:
        paths = [str(p) for p in corpus.getComposer(comp)]
        if a.limit:
            paths = paths[: a.limit]
        rows, t0 = [], time.time()
        for path in paths:
            try:
                loaded = load(path)
            except Exception as e:  # noqa: BLE001 - corpus has odd files; report and go on
                print(f"skip {path.rsplit('/', 1)[-1]}: {e}", file=sys.stderr)
                continue
            if loaded is None or loaded[2] > a.max_parts:
                continue
            m, truth, k = loaded
            if a.generic or k != 4:
                voices = [Voice(f"v{i}", "MELODY" if i == 0 else "BASS" if i == k - 1 else "INNER") for i in range(k)]
            else:
                voices = default_voices(4)
            assign, rep = separate(m, voices, Params(beam=a.beam))
            rows.append((path.rsplit("/", 1)[-1], len(m.notes), *score_piece(m, truth, assign, k)))
        if not rows:
            print(f"{comp}: nothing scored")
            continue
        col = lambda i: [r[i] for r in rows]  # noqa: E731
        print(f"{comp}: {len(rows)} pieces, {sum(col(1))} notes, {time.time() - t0:.0f}s")
        print(f"  note acc {statistics.mean(col(2)):.3f}   link P {statistics.mean(col(3)):.3f}   "
              f"R {statistics.mean(col(4)):.3f}   F1 mean {statistics.mean(col(5)):.3f}  median {statistics.median(col(5)):.3f}  "
              f"min {min(col(5)):.3f} ({min(rows, key=lambda r: r[5])[0]})")


if __name__ == "__main__":
    main()
