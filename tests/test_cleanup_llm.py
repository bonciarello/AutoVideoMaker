import pytest

from cleanup_llm import (OUTPUT_SCHEMA, WindowRejected, assign_candidates,
                         format_window, make_windows, validate_response)
from cleanup_rules import Candidate
from helpers import make_words


def _phrases_of(sizes):
    phrases, start = [], 0
    for size in sizes:
        phrases.append((start, start + size - 1))
        start += size
    return phrases


def test_make_windows_breaks_at_phrase_end_with_overlap():
    windows = make_windows(_phrases_of([10] * 100), 1000, window_words=300, overlap=30)
    assert windows[0] == (0, 299)
    assert windows[1][0] == 270
    assert windows[-1][1] == 999
    assert all(b - a + 1 <= 300 for a, b in windows)


def test_make_windows_single_block_for_short_transcript():
    assert make_windows(_phrases_of([5, 5]), 10) == [(0, 9)]


def test_make_windows_without_words():
    assert make_windows([], 0) == []


def test_assign_candidates_to_first_window_containing_them():
    windows = [(0, 299), (270, 599)]
    numbered = [(1, Candidate(10, 12, "repetition", False, "")),
                (2, Candidate(280, 281, "retake", False, "")),
                (3, Candidate(295, 305, "retake", False, ""))]
    assigned = assign_candidates(windows, numbered)
    assert [n for n, _ in assigned[0]] == [1, 2]
    assert [n for n, _ in assigned[1]] == [3]


def test_format_window_lists_numbered_words_pauses_and_candidates():
    words = make_words("Buongiorno a... Ciao a tutti", pauses={2: 1.4})
    text = format_window(words, (0, 4), 1, 2, [(1, Candidate(0, 1, "false_start", False, ""))])
    assert text.splitlines()[0] == "Blocco 1/2 · parole 0–4"
    assert "0:Buongiorno 1:a... [pausa 1,4 s] 2:Ciao 3:a 4:tutti" in text
    assert "C1: parole 0–1 · falsa partenza · «Buongiorno a...»" in text


def test_output_schema_is_strict():
    assert OUTPUT_SCHEMA["additionalProperties"] is False
    assert OUTPUT_SCHEMA["properties"]["cuts"]["items"]["required"] == ["from_id", "to_id", "kind", "sure", "reason"]


def _numbered_words(n):
    return make_words(" ".join(f"parola{i}" for i in range(n)))


def test_validate_keeps_valid_cuts_and_known_verdicts():
    words = _numbered_words(100)
    numbered = [(1, Candidate(10, 11, "repetition", False, ""))]
    data = {"verdicts": [{"candidate": 1, "cut": False, "sure": True},
                         {"candidate": 9, "cut": True, "sure": True}],
            "cuts": [{"from_id": 20, "to_id": 22, "kind": "self_correction", "sure": False, "reason": "riformula"}]}
    verdicts, cuts, warnings = validate_response(data, words, (0, 99), numbered)
    assert verdicts == {1: (False, True)}
    assert cuts == [Candidate(20, 22, "self_correction", False, "riformula", source="claude")]
    assert warnings == []


def test_validate_drops_cut_outside_window():
    words = _numbered_words(200)
    data = {"verdicts": [], "cuts": [{"from_id": 150, "to_id": 151, "kind": "repetition", "sure": True, "reason": "x"}]}
    verdicts, cuts, warnings = validate_response(data, words, (0, 99), [])
    assert cuts == [] and "fuori dal blocco" in warnings[0]


def test_validate_drops_cut_longer_than_30_seconds():
    words = _numbered_words(1000)          # 0,4 s per parola: 80 parole ≈ 32 s
    data = {"verdicts": [], "cuts": [{"from_id": 0, "to_id": 79, "kind": "retake", "sure": True, "reason": "x"}]}
    verdicts, cuts, warnings = validate_response(data, words, (0, 999), [])
    assert cuts == [] and "più lungo" in warnings[0]


def test_validate_rejects_window_when_claude_removes_too_much():
    words = _numbered_words(100)
    data = {"verdicts": [], "cuts": [{"from_id": 0, "to_id": 25, "kind": "retake", "sure": True, "reason": "x"}]}
    with pytest.raises(WindowRejected):
        validate_response(data, words, (0, 99), [])
