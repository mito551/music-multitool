from audiotoolkit.core.queue import BatchQueue, Status, gather_audio


def touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return str(p)


def test_duplicate_stems_get_unique_song_names(tmp_path):
    a, b = touch(tmp_path / "a" / "song.mp3"), touch(tmp_path / "b" / "song.mp3")
    c = touch(tmp_path / "c" / "song.flac")
    q = BatchQueue()
    items = q.add([a, b], "separate", {})
    items += q.add([c], "separate", {})
    assert [i.song for i in items] == ["song", "song (2)", "song (3)"]


def test_gather_audio_expands_folders_and_filters(tmp_path):
    f1 = touch(tmp_path / "d" / "x.WAV")
    f2 = touch(tmp_path / "d" / "sub" / "y.mp3")
    touch(tmp_path / "d" / "notes.txt")
    lone = touch(tmp_path / "z.flac")
    bad = touch(tmp_path / "w.txt")
    assert gather_audio([str(tmp_path / "d"), lone, bad]) == sorted([f1, f2]) + [lone]


def test_override_wins_in_effective_opts(tmp_path):
    q = BatchQueue()
    (item,) = q.add([touch(tmp_path / "a.mp3")], "convert", {"format": "wav", "channels": 2})
    q.set_override(item.id, {"format": "mp3"})
    assert q.effective_opts(item) == {"format": "mp3", "channels": 2}


def test_next_pending_order_and_skips_non_pending(tmp_path):
    q = BatchQueue()
    a, b = q.add([touch(tmp_path / "a.mp3"), touch(tmp_path / "b.mp3")], "midi", {})
    assert q.next_pending() is a
    q.mark(a.id, Status.RUNNING, fraction=0.2, message="go")
    assert (a.status, a.fraction, a.message) == (Status.RUNNING, 0.2, "go")
    assert q.next_pending() is b
    q.mark(b.id, Status.DONE)
    assert q.next_pending() is None


def test_retry_failed_resets_and_counts(tmp_path):
    q = BatchQueue()
    a, b, c = q.add([touch(tmp_path / f"{n}.mp3") for n in "abc"], "midi", {})
    q.mark(a.id, Status.FAILED, message="bad")
    q.mark(b.id, Status.CANCELLED)
    q.mark(c.id, Status.DONE)
    assert q.retry_failed() == 2
    assert [i.status for i in q.items] == [Status.PENDING, Status.PENDING, Status.DONE]
    assert a.message == ""


def test_remove(tmp_path):
    q = BatchQueue()
    a, b = q.add([touch(tmp_path / "a.mp3"), touch(tmp_path / "b.mp3")], "midi", {})
    q.remove(a.id)
    assert q.items == [b] and q.get(b.id) is b


def test_same_source_shares_song_dir_across_kinds(tmp_path):
    src = touch(tmp_path / "a" / "song.mp3")
    other = touch(tmp_path / "b" / "song.mp3")
    q = BatchQueue()
    first = q.add([src], "separate", {})[0]
    again = q.add([src], "lyrics", {})[0]
    diff = q.add([other], "lyrics", {})[0]
    assert first.song == again.song == "song" and diff.song == "song (2)"
