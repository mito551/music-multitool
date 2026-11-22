import mido

from musicmultitool.core.voicesep import Params, Voice, default_voices, read_midi, separate, write_midi

TPQ = 480
LINES = [  # soprano, alto, tenor, bass: stepwise lines, ranges well apart
    [72, 74, 76, 74, 72, 71, 72, 74],
    [64, 65, 67, 65, 64, 62, 64, 65],
    [55, 57, 59, 57, 55, 55, 55, 57],
    [43, 45, 47, 45, 43, 43, 43, 45],
]


def make(path, lines=LINES, jitter=0, legato=0):
    mid = mido.MidiFile(ticks_per_beat=TPQ)
    tr = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000, time=0)])
    ev = []
    for line in lines:
        for i, p in enumerate(line):
            on = i * TPQ + (jitter * (p % 3) if jitter else 0)
            ev += [(on, 1, p), (i * TPQ + TPQ + legato, 0, p)]
    ev.sort()
    last = 0
    for t, on, p in ev:
        tr.append(mido.Message("note_on" if on else "note_off", note=p, velocity=64 if on else 0, time=t - last))
        last = t
    mid.tracks.append(tr)
    mid.save(path)


def truth(m):
    return {n.id: next(v for v, line in enumerate(LINES) if n.pitch in line and n.pitch == line[(n.on + TPQ // 2) // TPQ])
            for n in m.notes}


def test_chorale_exact(tmp_path):
    p = str(tmp_path / "a.mid")
    make(p)
    m = read_midi(p)
    a, rep = separate(m, default_voices(4))
    assert rep["mode"] == "QUANTIZED"
    assert sorted(a) == [n.id for n in m.notes]  # conservation
    assert a == truth(m)


def test_performance_jitter_and_legato(tmp_path):
    p = str(tmp_path / "a.mid")
    make(p, jitter=8, legato=20)
    m = read_midi(p)
    a, rep = separate(m, default_voices(4))
    assert rep["mode"] == "PERFORMANCE"
    assert a == truth(m)


def test_deterministic_and_midi_roundtrip(tmp_path):
    p = str(tmp_path / "a.mid")
    make(p)
    m = read_midi(p)
    voices = default_voices(4)
    a1, _ = separate(m, voices)
    a2, _ = separate(m, voices)
    assert a1 == a2
    out = str(tmp_path / "v.mid")
    write_midi(m, voices, a1, out)
    back = mido.MidiFile(out)
    assert len(back.tracks) == 5 and back.ticks_per_beat == TPQ
    counts = [sum(1 for x in t if x.type == "note_on") for t in back.tracks[1:]]
    assert counts == [8, 8, 8, 8]


def test_overflow_keeps_every_note(tmp_path):
    p = str(tmp_path / "a.mid")
    make(p, LINES + [[60, 62, 64, 62, 60, 59, 60, 62]])
    m = read_midi(p)
    a, rep = separate(m, default_voices(4))
    assert sorted(a) == [n.id for n in m.notes] and len(rep["overflow_events"]) == 8


def test_single_voice(tmp_path):
    p = str(tmp_path / "a.mid")
    make(p)
    m = read_midi(p)
    a, _ = separate(m, [Voice("all")], Params(beam=4))
    assert set(a.values()) == {0} and len(a) == len(m.notes)
