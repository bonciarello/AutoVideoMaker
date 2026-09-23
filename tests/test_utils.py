from utils import CLAUDE_MODEL, normalize_word


def test_normalize_word_strips_edge_punctuation_and_lowercases():
    assert normalize_word("Non") == "non"
    assert normalize_word("è...") == "è"
    assert normalize_word("tutti,") == "tutti"
    assert normalize_word("«Ciao»") == "ciao"


def test_normalize_word_keeps_inner_apostrophe():
    assert normalize_word("Dall'alto") == "dall'alto"
    assert normalize_word("dall’alto") == "dall'alto"


def test_normalize_word_of_pure_punctuation_is_empty():
    assert normalize_word("...") == ""
    assert normalize_word("") == ""


def test_claude_model_is_opus_5():
    assert CLAUDE_MODEL == "claude-opus-5"
