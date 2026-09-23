from video_processing import MIN_SEGMENT_DURATION, clear_old_chunks, compute_keep_ranges


def test_keep_ranges_are_the_complement_of_all_cuts():
    keep = compute_keep_ranges([(0.0, 1.0), (5.0, 6.0)], [(2.0, 3.0), (2.5, 4.0)], 10.0)
    assert keep == [(1.0, 2.0), (4.0, 5.0), (6.0, 10.0)]


def test_keep_ranges_drop_segments_shorter_than_minimum():
    assert compute_keep_ranges([(0.0, 1.0)], [(1.0 + MIN_SEGMENT_DURATION / 2, 3.0)], 3.0) == []


def test_compute_keep_ranges_does_not_modify_inputs():
    silence = [(5.0, 6.0), (0.0, 1.0)]
    compute_keep_ranges(silence, [], 10.0)
    assert silence == [(5.0, 6.0), (0.0, 1.0)]


def test_clear_old_chunks_removes_only_chunk_files(tmp_path):
    (tmp_path / "c_0000.mp4").write_bytes(b"x")
    (tmp_path / "c_0183.mp4").write_bytes(b"x")
    (tmp_path / "note.txt").write_text("resta")
    clear_old_chunks(str(tmp_path))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["note.txt"]
