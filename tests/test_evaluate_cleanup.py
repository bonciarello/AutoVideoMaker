from tools.evaluate_cleanup import cuts_breakdown, edl_keep_ranges, evaluate, manual_keep_ranges


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
    assert m["covered_seconds"] == 1.0
    assert m["coverage"] == 0.5
    assert m["wrong_seconds"] == 1.0
    assert [b["label"] for b in m["buckets"]] == ["< 0,3 s", "0,3–1 s", "> 1 s"]
    assert m["buckets"][2]["seconds"] == 2.0


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
