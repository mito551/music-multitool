from audiotoolkit.core.tapper import Tapper, relation


def test_first_tap_returns_none():
    assert Tapper().tap(0.0) is None


def test_steady_taps_give_120():
    t = Tapper()
    results = [t.tap(x) for x in (0, 0.5, 1.0, 1.5)]
    assert results == [None, 120.0, 120.0, 120.0]


def test_gap_resets():
    t = Tapper()
    t.tap(0)
    t.tap(0.5)
    assert t.tap(3.0) is None and t.count == 1


def test_window_uses_last_eight_taps():
    t = Tapper()
    times = [0, 1, 2, 3, 4, 5] + [5.5, 6, 6.5, 7, 7.5, 8, 8.5]
    result = None
    for x in times:
        result = t.tap(x)
    assert result == 120.0


def test_reset_clears():
    t = Tapper()
    t.tap(0)
    t.tap(1)
    t.reset()
    assert t.count == 0 and t.tap(5) is None


def test_relation_cases():
    assert relation(120, 120) == "match" and relation(121, 120) == "match"
    assert relation(60, 120) == "half"
    assert relation(240, 120) == "double"
    assert relation(100, 120) == "off"
