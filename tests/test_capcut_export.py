import json
import os

from capcut_export import MARKER_COLOR, _unique_project_dir, build_draft, generate_capcut_project


def _video_info(duration=10.0, fps="30/1"):
    return {"format": {"duration": str(duration)},
            "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": fps},
                        {"codec_type": "audio", "channels": 2}]}


def _clip(path, keep, markers=None):
    return {"keep_ranges": keep, "video_path": path, "video_info": _video_info(), "markers": markers or []}


def _marks(draft):
    return draft["time_marks"]["mark_items"]


def test_build_draft_without_markers_keeps_time_marks_none(tmp_path):
    draft, meta, segments, fps = build_draft([_clip("/v/a.mov", [(0.0, 1.0), (2.0, 3.0)])],
                                             "P", str(tmp_path / "P"), str(tmp_path))
    assert draft["time_marks"] is None
    assert len(segments) == 2 and fps == 30.0


def test_marker_goes_on_the_join_after_the_cut(tmp_path):
    clip = _clip("/v/a.mov", [(0.0, 1.0), (2.0, 3.0)], markers=[{"source_time": 2.0, "title": "ripetizione: «che che»"}])
    draft, *_ = build_draft([clip], "P", str(tmp_path / "P"), str(tmp_path))
    assert _marks(draft)[0]["time_range"] == {"start": 1_000_000, "duration": 0}
    assert _marks(draft)[0]["title"] == "ripetizione: «che che»"
    assert _marks(draft)[0]["color"] == MARKER_COLOR


def test_marker_after_last_segment_goes_to_timeline_end(tmp_path):
    clip = _clip("/v/a.mov", [(0.0, 1.0)], markers=[{"source_time": 5.0, "title": "x"}])
    draft, *_ = build_draft([clip], "P", str(tmp_path / "P"), str(tmp_path))
    assert _marks(draft)[0]["time_range"]["start"] == 1_000_000


def test_markers_of_second_clip_are_offset_in_combined_project(tmp_path):
    first = _clip("/v/a.mov", [(0.0, 2.0)])
    second = _clip("/v/b.mov", [(0.0, 1.0), (3.0, 4.0)], markers=[{"source_time": 3.0, "title": "y"}])
    draft, *_ = build_draft([first, second], "P", str(tmp_path / "P"), str(tmp_path))
    assert _marks(draft)[0]["time_range"]["start"] == 3_000_000


def test_malformed_marker_is_skipped(tmp_path, capsys):
    clip = _clip("/v/a.mov", [(0.0, 1.0)], markers=[{"title": "senza tempo"}])
    draft, *_ = build_draft([clip], "P", str(tmp_path / "P"), str(tmp_path))
    assert draft["time_marks"] is None
    assert "marcatore ignorato" in capsys.readouterr().out


def test_unique_project_dir_never_reuses_existing(tmp_path):
    (tmp_path / "Video").mkdir()
    assert _unique_project_dir(str(tmp_path), "Video") == ("Video-2", str(tmp_path / "Video-2"))
    (tmp_path / "Video-2").mkdir()
    assert _unique_project_dir(str(tmp_path), "Video")[0] == "Video-3"


def test_generate_does_not_overwrite_existing_project(tmp_path):
    existing = tmp_path / "Video"
    existing.mkdir()
    (existing / "draft_info.json").write_text("montaggio manuale", encoding="utf-8")
    project_dir = generate_capcut_project([_clip("/v/a.mov", [(0.0, 1.0)])], "Video", drafts_root=str(tmp_path))
    assert project_dir == str(tmp_path / "Video-2")
    assert (existing / "draft_info.json").read_text(encoding="utf-8") == "montaggio manuale"
    draft = json.load(open(os.path.join(project_dir, "draft_info.json"), encoding="utf-8"))
    assert draft["name"] == "Video-2"
