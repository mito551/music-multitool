"""Fit the voice separator's cost weights by coordinate descent on link F1 (spec level A).

    PYTHONPATH=src python scripts/fit_voices.py --cache /tmp/vs.pkl --out profile.json

Training pieces come from the music21 corpus; held-out pieces (including a whole composer) are scored with the final weights.
Everything is deterministic: same corpus, same profile.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import pickle
import statistics
from multiprocessing import Pool

import eval_voices as ev
from music21 import corpus

from musicmultitool.core.voicesep import Midi, Params, Voice, default_voices, separate

MAXN = 500  # notes kept per piece: keeps one evaluation to seconds
TUNE = ["w_gap", "w_ovl_base", "w_ovl", "w_range", "w_cent", "w_role", "w_dyn", "w_vov"]
SPLITS = {  # name -> (composer, slice of its corpus list)
    "train": [("haydn", slice(0, 5)), ("mozart", slice(0, 8)), ("bach", slice(0, None, 7))],
    "valid": [("haydn", slice(5, 9)), ("mozart", slice(8, 16)), ("bach", slice(3, None, 7)), ("beethoven", slice(0, 8))],
}


def trim(m: Midi, truth: dict[int, int]) -> tuple[Midi, dict[int, int]]:
    notes = sorted(m.notes, key=lambda n: (n.on, -n.pitch))[:MAXN]
    return Midi(notes, m.tpq, [], m.tempos), {n.id: truth[n.id] for n in notes}


def build(path: str) -> list:
    data = {}
    for split, items in SPLITS.items():
        rows = []
        for comp, sl in items:
            for p in [str(x) for x in corpus.getComposer(comp)][sl][:60]:
                try:
                    loaded = ev.load(p)
                except Exception:  # noqa: BLE001
                    continue
                if loaded is None or loaded[2] > 6:
                    continue
                m, truth, k = loaded
                m, truth = trim(m, truth)
                rows.append((comp, os.path.basename(p), m, truth, k))
        data[split] = rows
    with open(path, "wb") as f:
        pickle.dump(data, f)
    return data


def one(args) -> float:
    (comp, name, m, truth, k), params = args
    voices = default_voices(4) if (comp == "bach" and k == 4) else [
        Voice(f"v{i}", "MELODY" if i == 0 else "BASS" if i == k - 1 else "INNER") for i in range(k)]
    assign, _ = separate(m, voices, params)
    return ev.score_piece(m, truth, assign, k)[3]


def objective(pool, rows, params) -> float:
    return statistics.mean(pool.map(one, [(r, params) for r in rows]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rounds", type=int, default=2)
    a = ap.parse_args()
    data = pickle.load(open(a.cache, "rb")) if os.path.exists(a.cache) else build(a.cache)
    train, valid = data["train"], data["valid"]
    print(f"train {len(train)} pieces, valid {len(valid)} pieces", flush=True)
    best = dataclasses.replace(Params(), beam=16)
    with Pool() as pool:
        base = objective(pool, train, best)
        print(f"start train F1 {base:.4f}", flush=True)
        for r in range(a.rounds):
            for name in TUNE:
                for mult in (0.25, 0.5, 2.0, 4.0):
                    cand = dataclasses.replace(best, **{name: getattr(best, name) * mult})
                    score = objective(pool, train, cand)
                    if score > base + 1e-4:
                        best, base = cand, score
                        print(f"round {r} {name} x{mult} -> {getattr(best, name):.3f}  train F1 {base:.4f}", flush=True)
        report = {}
        for split, rows in (("train", train), ("valid", valid)):
            for params, tag in ((dataclasses.replace(Params(), beam=16), "default"), (best, "fitted")):
                for comp in sorted({r[0] for r in rows}):
                    sub = [r for r in rows if r[0] == comp]
                    report[f"{split}/{comp}/{tag}"] = round(objective(pool, sub, params), 4)
    for k, v in report.items():
        print(k, v)
    weights = {f.name: getattr(best, f.name) for f in dataclasses.fields(best) if f.name in TUNE}
    json.dump({"weights": weights, "scores": report}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
