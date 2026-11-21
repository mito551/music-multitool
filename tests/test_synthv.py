from audiotoolkit.core.synthv import from_synthv, to_synthv


def test_next_syllable_then_continue():
    words = [(0.0, 2.0, "footprint"), (3.0, 3.5, "to")]
    notes = [(0.0, 0.4), (0.5, 0.9), (1.2, 1.3), (3.0, 3.4)]
    assert to_synthv(words, notes) == ("footprint + - to", 0)


def test_one_syllable_word_only_continues():
    assert to_synthv([(0.0, 1.0, "queen")], [(0.0, 0.4), (0.5, 0.9)]) == ("queen -", 0)


def test_syllable_counts():
    from audiotoolkit.core.synthv import syllables
    assert [syllables(w) for w in ("snow", "mountain", "tonight", "howling", "the", "make", "walked", "table", "isolation")] \
        == [1, 2, 2, 2, 1, 1, 1, 2, 4]


def test_word_without_note_is_kept():
    assert to_synthv([(0.0, 1.0, "a"), (2.0, 3.0, "b")], [(0.0, 1.0)]) == ("a b", 1)


def test_two_words_one_note_share_it():
    assert to_synthv([(0.0, 0.1, "a"), (0.05, 0.2, "b")], [(0.0, 0.3)]) == ("a b", 0)


def test_back_restores_original_layout():
    original = "Let it go, let it go\nCan't hold it back\n"
    synthv = "let it go + let it go - can't - hold it .b .ae .k"
    text, bad = from_synthv(synthv, original)
    assert text == original and bad == 0


def test_back_counts_respellings():
    text, bad = from_synthv("the wihnd is howling", "The wind is howling\n")
    assert text == "The wind is howling\n" and bad == 1


def _job(tmp_path, name, opts=None):
    from audiotoolkit.core.protocol import Job
    return Job("j", "lyrics", str(tmp_path / name), opts or {}, str(tmp_path / "out" / "song"))


def test_reverse_job_writes_clean_text(tmp_path):
    from audiotoolkit.worker.kinds.lyrics import run
    (tmp_path / "song.txt").write_text("Let it go\nCan't hold\n")
    (tmp_path / "song.synthv.txt").write_text("let it go + can't - hold")
    outputs, result = run(_job(tmp_path, "song.synthv.txt"), lambda *_: None)
    assert open(outputs[0].path).read() == "Let it go\nCan't hold\n" and outputs[0].path.endswith("song.clean.txt")
    assert result["unconfirmed"] == 0


def test_reverse_job_needs_original(tmp_path):
    import pytest
    from audiotoolkit.worker.kinds.lyrics import run
    (tmp_path / "song.synthv.txt").write_text("x")
    with pytest.raises(FileNotFoundError, match="original lyrics"):
        run(_job(tmp_path, "song.synthv.txt"), lambda *_: None)


def test_vocal_notes_prefers_vocals_midi(tmp_path):
    import os
    import pretty_midi
    from audiotoolkit.worker.kinds.lyrics import _vocal_notes
    job = _job(tmp_path, "song.wav")
    os.makedirs(os.path.join(job.out_dir, "midi"))
    for name, start in (("bass", 5.0), ("vocals", 1.0)):
        pm = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(0)
        inst.notes.append(pretty_midi.Note(80, 60, start, start + 0.5))
        pm.instruments.append(inst)
        pm.write(os.path.join(job.out_dir, "midi", f"{name}.mid"))
    assert _vocal_notes(job) == [(1.0, 1.5)]


def test_queue_lyrics_takes_synthv_txt(tmp_path):
    from audiotoolkit.core.queue import BatchQueue
    q = BatchQueue()
    items = q.add([str(tmp_path / "a.synthv.txt"), str(tmp_path / "b.txt"), str(tmp_path / "c.wav")], "lyrics", {})
    assert [i.song for i in items] == ["a", "c"]
    assert [i.song for i in BatchQueue().add([str(tmp_path / "a.synthv.txt")], "separate", {})] == []


def test_notes_outside_any_word_get_no_token():
    assert to_synthv([(0.0, 0.1, "a")], [(0.0, 0.1), (2.0, 2.1), (3.0, 3.1)]) == ("a", 0)
