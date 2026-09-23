import json

import pytest

from tools.evaluate_cleanup import (cuts_breakdown, cuts_touching, edl_keep_ranges, evaluate,
                                    load_labels, manual_keep_ranges, snap_to_frames, split_wrong)


def test_load_labels_reads_ok_and_no(tmp_path):
    path = tmp_path / "etichette.json"
    path.write_text(json.dumps({"tagli": [{"from_id": 23, "to_id": 24, "label": "ok"},
                                          {"from_id": 7, "to_id": 7, "label": "no"}]}), encoding="utf-8")
    assert load_labels(str(path)) == {(23, 24): "ok", (7, 7): "no"}


def test_load_labels_without_file_is_empty(tmp_path):
    assert load_labels(str(tmp_path / "etichette.json")) == {}


def test_load_labels_rejects_unknown_label(tmp_path):
    path = tmp_path / "etichette.json"
    path.write_text(json.dumps({"tagli": [{"from_id": 1, "to_id": 1, "label": "forse"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="forse"):
        load_labels(str(path))


def _three_cuts():
    from cleanup import CleanupCut
    return [CleanupCut(1, 1, "false_start", True, "claude", "", "a", 1.0, 2.0),
            CleanupCut(3, 3, "repetition", True, "rule", "", "b", 3.0, 4.0),
            CleanupCut(5, 5, "repetition", True, "rule", "", "c", 5.0, 6.0)]


def test_split_wrong_assigns_each_tract_to_one_cause():
    # 1,5–2 è sia nel taglio «no» sia in una pausa: conta come errore;
    # 3,5–4 è sia nel taglio «ok» sia in una pausa: conta come approvato.
    parts = split_wrong(wrong=[(1.0, 2.5), (3.0, 4.5), (5.0, 6.0), (8.0, 9.0)], cleanup_cuts=_three_cuts(),
                        pause_cuts=[(1.5, 2.5), (3.5, 4.5)], labels={(1, 1): "no", (3, 3): "ok"}, fps=100.0)
    assert parts == {"no": [(1.0, 2.0)], "unlabeled": [(5.0, 6.0)], "ok": [(3.0, 4.0)],
                     "pause": [(2.0, 2.5), (4.0, 4.5)], "other": [(8.0, 9.0)]}


def test_cuts_touching_lists_cuts_with_seconds_inside():
    cuts = _three_cuts()
    assert cuts_touching([(5.5, 7.0), (1.99, 3.0)], cuts, fps=100.0, min_len=0.025) == [(cuts[2], 0.5)]


def test_manual_keep_ranges_reads_video_segments_of_the_right_file():
    draft = {"materials": {"videos": [{"id": "A", "path": "/x/clip.mov"}, {"id": "B", "path": "/x/altro.mov"}]},
             "tracks": [{"type": "video", "segments": [
                 {"material_id": "A", "source_timerange": {"start": 1_000_000, "duration": 2_000_000}},
                 {"material_id": "B", "source_timerange": {"start": 0, "duration": 5_000_000}}]},
                        {"type": "audio", "segments": []}]}
    assert manual_keep_ranges(draft, "clip.mov") == [(1.0, 3.0)]


def test_edl_keep_ranges_parses_source_timecodes(tmp_path):
    edl = tmp_path / "auto.edl"
    edl.write_text("TITLE: Video Processed\nFCM: NON-DROP FRAME\n\n"
                   "001  AX       AA/V  C        00:00:08:30 00:00:09:00 00:00:00:00 00:00:00:30\n"
                   "* FROM CLIP NAME: clip.mov\n", encoding="utf-8")
    assert edl_keep_ranges(str(edl), 60.0) == [(8.5, 9.0)]


def test_evaluate_coverage_and_extra_cuts():
    m = evaluate(manual_keep=[(0.0, 2.0), (4.0, 10.0)],   # a mano: tolti 2–4
                 auto_keep=[(0.0, 10.0)],                 # la versione automatica non tagliava niente
                 new_keep=[(0.0, 3.0), (4.0, 9.0)],       # nuova pipeline: tolti 3–4 e 9–10
                 duration=10.0)
    assert m["extra_seconds"] == 2.0
    assert m["extra"] == [(2.0, 4.0)]
    assert m["covered_seconds"] == 1.0
    assert m["coverage"] == 0.5
    assert m["wrong_seconds"] == 1.0
    assert [b["label"] for b in m["buckets"]] == ["< 0,3 s", "0,3–1 s", "> 1 s"]
    assert m["buckets"][2]["seconds"] == 2.0


def test_snap_to_frames():
    assert snap_to_frames([(0.004, 1.009)], 100.0) == [(0.0, 1.01)]


def test_evaluate_ignores_frame_slivers():
    m = evaluate(manual_keep=[(0.0, 2.0), (4.0, 10.0)], auto_keep=[(0.0, 10.0)],
                 new_keep=[(0.0, 1.99), (4.01, 10.0)], duration=10.0, min_len=0.025)
    assert m["wrong_seconds"] == 0.0
    assert m["coverage"] == 1.0


def test_cuts_breakdown_by_type_and_origin():
    from cleanup import CleanupCut
    cuts = [CleanupCut(0, 1, "false_start", False, "rule", "", "x", 2.0, 3.0),
            CleanupCut(5, 5, "repetition", True, "claude", "", "y", 9.0, 9.5)]
    rows = cuts_breakdown(cuts, pause_cuts=[(3.0, 3.5)], extra=[(2.0, 4.0)], manual_removed=[(2.0, 4.0)])
    by_key = {(r["kind"], r["source"]): r for r in rows}
    assert by_key[("false_start", "rule")]["useful"] == 1.0
    assert by_key[("false_start", "rule")]["wrong"] == 0.0
    assert by_key[("repetition", "claude")]["wrong"] == 0.5
    assert by_key[("pause", "pause")]["useful"] == 0.5


def test_main_runs_end_to_end_in_rules_mode(tmp_path, monkeypatch):
    import json
    import sys
    import wave

    from helpers import make_words
    from tools import evaluate_cleanup

    folder = tmp_path / "video"
    bench = folder / "banco-prova"
    (bench / "capcut-manuale").mkdir(parents=True)
    words = make_words("una delle delle aziende. Io credo che sia giusto. Io credo che sia giusto e utile.")
    duration = words[-1]["end"] + 1.0
    (folder / "words.json").write_text(json.dumps({
        "version": 1, "video": {"name": "clip.mov", "size": 1, "duration": duration},
        "transcriber": "deepgram", "model": "nova-3", "language": "it", "text": "", "words": words}),
        encoding="utf-8")
    draft = {"fps": 30.0, "materials": {"videos": [{"id": "A", "path": "/x/clip.mov"}]},
             "tracks": [{"type": "video", "segments": [
                 {"material_id": "A", "source_timerange": {"start": 0, "duration": int(duration * 1_000_000)}}]}]}
    (bench / "capcut-manuale" / "draft_info.json").write_text(json.dumps(draft), encoding="utf-8")
    (bench / "auto-originale.edl").write_text(
        "TITLE: x\nFCM: NON-DROP FRAME\n\n"
        "001  AX       AA/V  C        00:00:00:00 00:00:05:00 00:00:00:00 00:00:05:00\n", encoding="utf-8")
    with wave.open(str(bench / "audio_analisi.wav"), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * duration))
    monkeypatch.setattr(sys, "argv", ["evaluate_cleanup.py", str(folder), "--mode", "rules"])

    evaluate_cleanup.main()

    results = list(bench.glob("risultati-*.md"))
    assert len(results) == 1
    report = results[0].read_text(encoding="utf-8")
    assert "| Tipo | Origine |" in report
    # a mano non è stato tolto niente: il taglio di «delle» (parola 1) è da etichettare
    assert "## Da etichettare" in report
    assert "- 1–1 (ripetizione, rule)" in report
