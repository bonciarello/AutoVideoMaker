from intervals import complement, intersect, measure, subtract, union


def test_union_merges_overlapping_and_adjacent():
    assert union([(3, 4), (0, 1), (1, 2), (3.5, 5)]) == [(0, 2), (3, 5)]


def test_union_drops_empty_intervals():
    assert union([(1, 1), (2, 1.5)]) == []


def test_measure_counts_overlaps_once():
    assert measure([(0, 2), (1, 3)]) == 3


def test_complement_within_duration():
    assert complement([(1, 2), (4, 6)], 5) == [(0, 1), (2, 4)]


def test_complement_of_nothing_is_everything():
    assert complement([], 3) == [(0, 3)]


def test_intersect():
    assert intersect([(0, 5)], [(1, 2), (4, 7)]) == [(1, 2), (4, 5)]


def test_subtract():
    assert subtract([(0, 5)], [(1, 2), (4, 7)]) == [(0, 1), (2, 4)]
