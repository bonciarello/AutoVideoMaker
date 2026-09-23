import json

from cleanup import CleanupCut, CleanupResult, context_text, fmt_time, write_report
from helpers import make_words


def test_fmt_time():
    assert fmt_time(0) == "00:00,0"
    assert fmt_time(75.26) == "01:15,3"
    assert fmt_time(3725.0) == "1:02:05,0"


def test_context_text_marks_removed_words():
    words = make_words("uno due tre quattro cinque sei sette otto")
    assert context_text(words, 3, 4, around=2) == "…due tre **[quattro cinque]** sei sette…"


def test_context_text_at_start_has_no_leading_ellipsis():
    words = make_words("Buongiorno a... Ciao a tutti")
    assert context_text(words, 0, 1, around=2) == "**[Buongiorno a...]** Ciao a…"


def test_write_report_creates_markdown_and_json(tmp_path):
    words = make_words("Buongiorno a... Ciao a tutti, questo è un test")
    cut = CleanupCut(from_id=0, to_id=1, kind="false_start", sure=False, source="rule",
                     reason="frase interrotta | riformulata", text="Buongiorno a...", start=0.0, end=0.8)
    result = CleanupResult(mode="rules", cuts=[cut], kept=[], warnings=["blocco 1/1 senza Claude: prova"])
    md_path, json_path = write_report(str(tmp_path), "clip.mov", result, words,
                                      keep_ranges=[(0.8, 3.5)], video_duration=4.0, pause_cuts=[(3.5, 4.0)])
    md = open(md_path, encoding="utf-8").read()
    assert "# Pulizia take — clip.mov" in md
    assert "- Durata: 00:04,0 → 00:02,7" in md
    assert "- Tolto dalle pause: 00:00,5" in md
    assert "- Tolto dalla pulizia (oltre alle pause): 00:00,8" in md
    assert "| 00:00,0 | falsa partenza | dubbio | regola |" in md
    assert "frase interrotta \\| riformulata" in md
    assert "blocco 1/1 senza Claude: prova" in md
    data = json.load(open(json_path, encoding="utf-8"))
    assert data["mode"] == "rules"
    assert data["cuts"][0]["timeline_time"] == 0.0
    assert data["cuts"][0]["text"] == "Buongiorno a..."
