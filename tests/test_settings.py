from audiotoolkit.core.settings import Settings, load_settings, save_settings


def test_defaults_when_missing(tmp_path):
    s = load_settings(str(tmp_path / "nope.json"))
    assert s == Settings() and s.out_root.endswith("Music/audio-toolkit") and s.skip_existing is True


def test_roundtrip(tmp_path):
    path = str(tmp_path / "sub" / "settings.json")
    s = Settings(out_root="/x", skip_existing=False, device="cpu", tab_opts={"separate": {"shifts": 2}})
    save_settings(s, path)
    assert load_settings(path) == s


def test_corrupt_file_gives_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{oops")
    assert load_settings(str(p)) == Settings()
