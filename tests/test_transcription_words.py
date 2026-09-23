from types import SimpleNamespace

import transcription
from transcription import deepgram_words, load_words_json, save_words_json, whisper_words


def _dg(word, start, end, punctuated=None, confidence=0.9):
    item = SimpleNamespace(word=word, start=start, end=end, confidence=confidence)
    if punctuated is not None:
        item.punctuated_word = punctuated
    return item


def test_deepgram_words_keep_punctuated_text_and_ids():
    words = deepgram_words([_dg("buongiorno", 8.0, 8.5, "Buongiorno"),
                            _dg("a", 8.5, 8.7, "a..."),
                            _dg("ciao", 9.9, 10.2, "Ciao")])
    assert [w["id"] for w in words] == [0, 1, 2]
    assert words[1]["text"] == "a..."
    assert words[1]["word"] == "a"
    assert words[2]["start"] == 9.9
    assert words[0]["confidence"] == 0.9


def test_deepgram_words_without_punctuated_word_fall_back_to_word():
    assert deepgram_words([_dg("ciao", 0.0, 0.3)])[0]["text"] == "ciao"


def test_whisper_words_skip_empty_tokens_and_renumber():
    segments = [{"words": [{"word": " Non", "start": 0.0, "end": 0.2, "probability": 0.8},
                           {"word": "  ", "start": 0.2, "end": 0.3},
                           {"word": " è...", "start": 0.3, "end": 0.5, "probability": 0.7}]}]
    words = whisper_words(segments)
    assert [(w["id"], w["word"], w["text"]) for w in words] == [(0, "non", "Non"), (1, "è", "è...")]


def test_transcribe_audio_reports_which_service_was_used(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_deepgram", lambda *a, **k: {"text": "", "words": []})
    monkeypatch.setattr(transcription, "transcribe_whisper", lambda *a, **k: {"text": "ciao", "words": []})
    result = transcription.transcribe_audio("x.wav", transcriber="deepgram", whisper_model="medium")
    assert (result["transcriber"], result["model"]) == ("whisper", "medium")


def _video(tmp_path, name="clip.mov", size=10):
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    return str(path)


def _transcription():
    return {"text": "Ciao a tutti",
            "words": [{"id": 0, "start": 0.0, "end": 0.3, "word": "ciao", "text": "Ciao", "confidence": 0.9}],
            "transcriber": "deepgram", "model": "nova-3"}


def test_words_json_roundtrip(tmp_path):
    video = _video(tmp_path)
    path = str(tmp_path / "words.json")
    save_words_json(path, _transcription(), video, 12.34, "it")
    loaded = load_words_json(path, video, 12.3, "deepgram", "it")
    assert loaded["text"] == "Ciao a tutti"
    assert loaded["words"][0]["text"] == "Ciao"
    assert loaded["transcriber"] == "deepgram"


def test_words_json_is_reused_after_video_moves_to_output_folder(tmp_path):
    video = _video(tmp_path)
    path = str(tmp_path / "words.json")
    save_words_json(path, _transcription(), video, 12.34, "it")
    (tmp_path / "output").mkdir()
    moved = tmp_path / "output" / "clip.mov"
    (tmp_path / "clip.mov").rename(moved)
    assert load_words_json(path, str(moved), 12.34, "deepgram", "it") is not None


def test_words_json_rejected_when_video_or_options_differ(tmp_path):
    video = _video(tmp_path)
    path = str(tmp_path / "words.json")
    save_words_json(path, _transcription(), video, 12.34, "it")
    assert load_words_json(path, _video(tmp_path, size=11), 12.34, "deepgram", "it") is None
    video = _video(tmp_path, size=10)
    assert load_words_json(path, video, 20.0, "deepgram", "it") is None
    assert load_words_json(path, video, 12.34, "whisper", "it") is None
    assert load_words_json(path, video, 12.34, "deepgram", "en") is None


def test_words_json_corrupted_or_missing_returns_none(tmp_path):
    video = _video(tmp_path)
    path = tmp_path / "words.json"
    assert load_words_json(str(path), video, 1.0, "deepgram", "it") is None
    path.write_text("{non è json", encoding="utf-8")
    assert load_words_json(str(path), video, 1.0, "deepgram", "it") is None
