from musicmultitool.core.protocol import (
    Done, Failed, Job, Output, Progress, decode_event, decode_job, encode_event, encode_job,
)


def test_job_roundtrip_with_spaces_and_unicode():
    job = Job("j1", "convert", "/m/Café Músic/né 1.mp3", {"a": {"b": [1, 2]}, "c": None}, "/out/né 1")
    assert decode_job(encode_job(job)) == job


def test_each_event_roundtrips():
    events = [
        Progress("j1", None, "working"),
        Progress("j1", 0.5),
        Done("j1", (Output("midi", "/o/a.mid"), Output("stem:vocals", "/o/v.wav")), {"k": 1}),
        Failed("j1", "boom"),
    ]
    for ev in events:
        assert decode_event(encode_event(ev)) == ev


def test_encoded_line_has_no_newline():
    job = Job("j1", "convert", "/a\nb.mp3", {}, "/o")
    assert "\n" not in encode_job(job)
    assert "\n" not in encode_event(Failed("j1", "line1\nline2"))
