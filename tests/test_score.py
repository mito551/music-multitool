import os
import xml.etree.ElementTree as ET

import pytest

from audiotoolkit.core.outputs import output_path
from audiotoolkit.core.protocol import Job
from audiotoolkit.worker.kinds.score import parse_pages, run

COPISTERIA = os.path.join(os.path.dirname(__file__), "..", "..", "copisteria")


def test_parse_pages():
    assert parse_pages("all", 4) == [1, 2, 3, 4]
    assert parse_pages("", 3) == [1, 2, 3]
    assert parse_pages("2-3", 5) == [2, 3]
    assert parse_pages("2", 5) == [2]
    assert parse_pages("3-99", 5) == [3, 4, 5]
    with pytest.raises(ValueError):
        parse_pages("9", 5)
    with pytest.raises(ValueError):
        parse_pages("x", 5)


def test_score_output_goes_in_score_folder(tmp_path):
    job = Job("j", "score", "/a/b.pdf", {}, str(tmp_path))
    assert output_path(job, "score", "musicxml", "b_p01") == str(tmp_path / "score" / "b_p01.musicxml")


@pytest.mark.slow
def test_pdf_page_becomes_musicxml(tmp_path):
    pdf = os.path.join(COPISTERIA, "tests", "data", "rotated.pdf")
    job = Job("j", "score", pdf, {"pages": "1"}, str(tmp_path / "out"))
    outputs, result = run(job, lambda frac, note="": None)
    assert [o.role for o in outputs] == ["score"]
    assert ET.parse(outputs[0].path).getroot().tag.startswith("score-")
    assert result["pages"] == 1
