from audiotoolkit.worker.kinds.lyrics import format_lrc, format_srt, format_txt


def test_srt_exact():
    segs = [(1.5, 3.0, "hi"), (3.25, 4.0, "yo")]
    assert format_srt(segs) == (
        "1\n00:00:01,500 --> 00:00:03,000\nhi\n\n"
        "2\n00:00:03,250 --> 00:00:04,000\nyo\n\n"
    )


def test_srt_hours():
    assert "01:01:01,001 --> 01:01:02,000" in format_srt([(3661.001, 3662.0, "x")])


def test_lrc_exact():
    assert format_lrc([(65.5, 67.0, "hi")]) == "[01:05.50]hi\n"


def test_txt_lines():
    assert format_txt([(0, 1, " hello "), (1, 2, "world")]) == "hello\nworld\n"


def test_empty_segments_give_empty_strings():
    assert format_srt([]) == format_lrc([]) == format_txt([]) == ""
