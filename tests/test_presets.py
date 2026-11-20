from pathlib import Path

from audiotoolkit.core.presets import Preset, Step, load_presets, save_preset, select_inputs, validate_preset
from audiotoolkit.core.protocol import Output

KINDS = ["convert", "analyze", "separate", "midi", "lyrics"]
BUILTIN = str(Path(__file__).resolve().parents[1] / "presets")
STEMS = [Output(f"stem:{n}", f"/o/stems/{n}.wav") for n in ("vocals", "drums", "bass")]


def test_select_source():
    assert select_inputs(Step("convert"), "/in/a.mp3", []) == ["/in/a.mp3"]


def test_select_pattern_fans_out():
    prev = STEMS + [Output("midi", "/o/m.mid")]
    assert select_inputs(Step("midi", {}, "stem:*"), "/in/a.mp3", prev) == [o.path for o in STEMS]


def test_select_exact_role():
    assert select_inputs(Step("lyrics", {}, "stem:vocals"), "/in/a.mp3", STEMS) == ["/o/stems/vocals.wav"]


def test_validate_errors():
    assert validate_preset(Preset("p", ()), KINDS) == ["no steps"]
    errs = validate_preset(Preset("p", (Step("nope", {}, "stem:*"),)), KINDS)
    assert "unknown kind: nope" in errs and "first step input must be 'source'" in errs
    assert validate_preset(Preset("p", (Step("convert"), Step("separate", {}, "audio"))), KINDS) == []


def test_builtins_all_valid(tmp_path):
    presets = load_presets(BUILTIN, str(tmp_path))
    assert len(presets) == 4
    for p in presets.values():
        assert validate_preset(p, KINDS) == [], p.name


def test_user_overrides_builtin(tmp_path):
    name = next(iter(load_presets(BUILTIN, str(tmp_path))))
    save_preset(str(tmp_path), Preset(name, (Step("convert"),)))
    assert load_presets(BUILTIN, str(tmp_path))[name].steps == (Step("convert"),)


def test_save_load_roundtrip(tmp_path):
    p = Preset("My chain", (Step("convert", {"loudnorm": -14}), Step("separate", {"stems": "vocals"}, "audio")))
    save_preset(str(tmp_path), p)
    assert load_presets(str(tmp_path / "none"), str(tmp_path))["My chain"] == p


def test_invalid_file_skipped(tmp_path):
    (tmp_path / "bad.json").write_text("{not json")
    assert load_presets(str(tmp_path), str(tmp_path / "none")) == {}
