import json
from types import SimpleNamespace

import numpy as np

from cleanup import (Energy, canonical_repetition, cut_end_time, cut_start_time,
                     marker_title, merge_applied, resolve_outcomes, run_cleanup,
                     source_to_timeline)
from cleanup_llm import LlmResult
from cleanup_rules import Candidate, normalized
from helpers import make_words


def test_energy_quietest_picks_minimum_rms_frame():
    energy = Energy(np.array([5, 5, 5, 1, 5, 5], dtype=np.float32), 0.01)
    assert abs(energy.quietest(0.0, 0.06) - 0.035) < 1e-9


def test_energy_quietest_clamps_to_interval():
    energy = Energy(np.array([5, 1, 5, 5], dtype=np.float32), 0.01)
    assert 0.02 <= energy.quietest(0.02, 0.04) <= 0.04


def _three_words(prev_end, next_start):
    return [{"id": 0, "start": 0.0, "end": prev_end, "word": "a", "text": "a", "confidence": 1},
            {"id": 1, "start": next_start, "end": next_start + 0.3, "word": "b", "text": "b", "confidence": 1},
            {"id": 2, "start": next_start + 0.4, "end": next_start + 0.7, "word": "c", "text": "c", "confidence": 1}]


def test_cut_start_in_long_pause_leaves_pad_after_kept_word():
    assert 1.05 <= cut_start_time(_three_words(1.0, 1.5), 1, pad=0.05, energy=None) <= 1.5


def test_cut_start_uses_quietest_point_of_the_pause():
    rms = np.full(200, 10.0, dtype=np.float32)
    rms[120] = 0.5                                 # 1,20–1,21 s
    t = cut_start_time(_three_words(1.0, 1.5), 1, pad=0.05, energy=Energy(rms, 0.01))
    assert abs(t - 1.205) < 1e-9


def test_cut_start_between_touching_words_stays_near_boundary():
    assert abs(cut_start_time(_three_words(1.0, 1.01), 1, pad=0.05, energy=None) - 1.005) < 1e-9


def test_cut_with_overlapping_timestamps_stays_within_30ms():
    words = _three_words(1.05, 1.0)                # la parola finisce dopo l'inizio della successiva
    t = cut_start_time(words, 1, pad=0.05, energy=Energy(np.full(300, 1.0, dtype=np.float32), 0.01))
    assert 0.995 <= t <= 1.055


def test_cut_at_video_start_and_end():
    words = make_words("uno due tre")
    assert cut_start_time(words, 0, pad=0.05, energy=None) == 0.0
    assert cut_end_time(words, 2, pad=0.05, energy=None, video_duration=9.0) == 9.0


def test_cut_end_in_long_pause_leaves_pad_before_next_word():
    assert 1.0 <= cut_end_time(_three_words(1.0, 1.5), 0, pad=0.05, energy=None, video_duration=9.0) <= 1.45


def test_resolve_outcomes_follows_the_table():
    sure = Candidate(0, 0, "repetition", True, "")
    dub_cut_sure = Candidate(2, 2, "repetition", False, "")
    dub_cut_unsure = Candidate(4, 4, "repetition", False, "")
    dub_keep = Candidate(6, 6, "retake", False, "")
    dub_no_verdict = Candidate(8, 8, "retake", False, "")
    dubious = [dub_cut_sure, dub_cut_unsure, dub_keep, dub_no_verdict]
    new_cut = Candidate(10, 11, "self_correction", False, "", source="claude")
    llm = LlmResult(verdicts={1: (True, True), 2: (True, False), 3: (False, True)},
                    cuts=[new_cut], warnings=[], failed_windows=0)
    applied, kept = resolve_outcomes([sure] + dubious, dubious, llm)
    assert [(c.from_id, marker) for c, marker in applied] == [(0, False), (2, False), (4, True), (8, True), (10, True)]
    assert kept == [dub_keep]


def test_resolve_outcomes_without_claude_marks_every_dubious():
    dub = Candidate(2, 3, "false_start", False, "")
    assert resolve_outcomes([dub], [dub], None) == ([(dub, True)], [])


def test_merge_applied_unions_duplicates_and_overlaps():
    rule = Candidate(1, 2, "false_start", True, "ripartenza")
    claude_dup = Candidate(1, 2, "false_start", True, "doppione", source="claude")
    claude_overlap = Candidate(2, 4, "self_correction", False, "riformula", source="claude")
    far = Candidate(9, 9, "repetition", True, "")
    groups = merge_applied([(claude_overlap, True), (rule, False), (claude_dup, False), (far, False)])
    assert [(g["from_id"], g["to_id"]) for g in groups] == [(1, 4), (9, 9)]
    assert len(groups[0]["parts"]) == 3


def test_source_to_timeline_collapses_cuts_on_the_join():
    keep = [(0.0, 2.0), (3.0, 5.0)]
    assert source_to_timeline(1.0, keep) == 1.0
    assert source_to_timeline(2.5, keep) == 2.0
    assert source_to_timeline(3.0, keep) == 2.0
    assert source_to_timeline(9.0, keep) == 4.0


def test_marker_title_truncates_long_text():
    assert marker_title("repetition", "molto molto") == "ripetizione: «molto molto»"
    long = marker_title("retake", "Allora quello che volevo dire davvero è che il modello funziona bene")
    assert len(long) <= 60 and long.endswith("…»")


def test_run_cleanup_rules_mode_applies_dubious_with_markers():
    words = make_words("Buongiorno a... Ciao a tutti, questo è un test. una delle delle aziende")
    result = run_cleanup(words, mode="rules", cue_word="rifaccio", audio_path=None, video_duration=10.0, pad=0.05)
    assert [(c.from_id, c.to_id, c.kind, c.sure) for c in result.cuts] == [
        (0, 1, "false_start", False), (10, 10, "repetition", True)]
    assert result.cuts[0].text == "Buongiorno a..."
    assert result.markers() == [{"source_time": result.cuts[0].end, "title": "falsa partenza: «Buongiorno a...»"}]
    stutter = result.cuts[1]
    assert words[9]["end"] < stutter.start <= words[10]["start"]
    assert words[10]["end"] <= stutter.end < words[11]["start"]


def test_run_cleanup_full_without_client_falls_back_to_rules():
    result = run_cleanup(make_words("una delle delle aziende"), mode="full", cue_word="rifaccio",
                         audio_path=None, video_duration=5.0, pad=0.05, client=None)
    assert result.mode == "rules"
    assert "ANTHROPIC_API_KEY" in result.warnings[0]


def test_run_cleanup_warns_when_a_cut_is_too_short():
    words = [{"id": 0, "start": 0.0, "end": 0.005, "word": "che", "text": "che", "confidence": 1},
             {"id": 1, "start": 0.005, "end": 0.3, "word": "che", "text": "che", "confidence": 1},
             {"id": 2, "start": 0.4, "end": 0.7, "word": "bello", "text": "bello", "confidence": 1}]
    result = run_cleanup(words, mode="rules", cue_word="rifaccio", audio_path=None,
                         video_duration=1.0, pad=0.05)
    assert result.cuts == []
    assert any("troppo corto" in w for w in result.warnings)


def test_run_cleanup_without_words_returns_empty_and_skips_claude():
    class Boom:
        @property
        def beta(self):
            raise AssertionError("Claude non deve essere chiamato")

    result = run_cleanup([], mode="full", cue_word="rifaccio", audio_path=None,
                         video_duration=5.0, pad=0.05, client=Boom())
    assert result.cuts == [] and result.kept == []


class _OneReplyClient:
    """Client finto: ogni richiesta riceve la stessa risposta JSON."""

    def __init__(self, data):
        reply = SimpleNamespace(stop_reason="end_turn",
                                content=[SimpleNamespace(type="text", text=json.dumps(data))])
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: reply))


def test_canonical_repetition_moves_claude_cut_to_the_first_occurrence():
    norm = normalized(make_words("Lui dice che che si è dimesso"))
    second = Candidate(3, 3, "repetition", True, "", source="claude")
    both = Candidate(2, 3, "repetition", True, "", source="claude")
    other = Candidate(4, 5, "false_start", True, "", source="claude")
    assert (canonical_repetition(second, norm).from_id, canonical_repetition(second, norm).to_id) == (2, 2)
    assert (canonical_repetition(both, norm).from_id, canonical_repetition(both, norm).to_id) == (2, 2)
    assert canonical_repetition(other, norm) == other


def test_rule_and_claude_on_the_same_stutter_keep_one_occurrence():
    words = make_words("Lui dice che che si è dimesso da Anthropic")
    client = _OneReplyClient({"verdicts": [], "cuts": [
        {"from_id": 3, "to_id": 3, "kind": "repetition", "sure": True, "reason": "inciampo"}]})
    result = run_cleanup(words, mode="full", cue_word="rifaccio", audio_path=None,
                         video_duration=10.0, pad=0.05, client=client)
    assert [(c.from_id, c.to_id) for c in result.cuts] == [(2, 2)]


def test_triple_repetition_still_keeps_the_last_occurrence_with_claude():
    words = make_words("che che che bello davvero oggi qui con tutti voi amici")
    client = _OneReplyClient({"verdicts": [], "cuts": [
        {"from_id": 1, "to_id": 2, "kind": "repetition", "sure": True, "reason": "inciampo"}]})
    result = run_cleanup(words, mode="full", cue_word="rifaccio", audio_path=None,
                         video_duration=10.0, pad=0.05, client=client)
    assert [(c.from_id, c.to_id) for c in result.cuts] == [(0, 1)]
