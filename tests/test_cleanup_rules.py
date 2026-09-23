from cleanup_rules import (Candidate, ends_with_ellipsis, find_false_starts,
                           find_repetitions, split_phrases)
from helpers import make_words


def test_split_phrases_on_punctuation_and_long_pauses():
    words = make_words("Ciao a tutti. Oggi parliamo di IA", pauses={6: 0.8})
    assert split_phrases(words) == [(0, 2), (3, 5), (6, 6)]


def test_split_phrases_ellipsis_closes_phrase():
    assert split_phrases(make_words("Buongiorno a... Ciao a tutti")) == [(0, 1), (2, 4)]


def test_ends_with_ellipsis():
    assert ends_with_ellipsis("a...")
    assert ends_with_ellipsis("verso…")
    assert not ends_with_ellipsis("tutti.")


def test_false_start_with_repeated_words_is_sure():
    words = make_words("Però non è... Non è il massimo")
    assert find_false_starts(words) == [Candidate(1, 2, "false_start", True, "ripartenza con le stesse parole")]


def test_short_false_start_with_different_words_is_dubious():
    words = make_words("Buongiorno a... Ciao a tutti")
    assert find_false_starts(words) == [Candidate(0, 1, "false_start", False, "frase interrotta e riformulata")]


def test_long_rephrased_fragment_is_left_to_claude():
    words = make_words("questa visione della webcam dall'alto verso... Dal basso verso l'alto")
    assert find_false_starts(words) == []


def test_ellipsis_on_last_word_is_ignored():
    assert find_false_starts(make_words("e così via...")) == []


def test_repeated_function_word_is_sure():
    assert find_repetitions(make_words("una delle delle 2 aziende")) == [
        Candidate(1, 1, "repetition", True, "parola ripetuta")]


def test_repeated_content_word_is_dubious():
    assert find_repetitions(make_words("è molto molto bello")) == [
        Candidate(1, 1, "repetition", False, "parola ripetuta")]


def test_emphatic_repetition_is_never_cut():
    assert find_repetitions(make_words("no no, grazie")) == []
    assert find_repetitions(make_words("piano piano arriviamo")) == []


def test_repeated_group_of_words_is_sure():
    assert find_repetitions(make_words("che si è che si è detto")) == [
        Candidate(0, 2, "repetition", True, "gruppo di parole ripetuto")]


def test_triple_repetition_keeps_only_the_last():
    assert find_repetitions(make_words("che che che bello")) == [
        Candidate(0, 0, "repetition", True, "parola ripetuta"),
        Candidate(1, 1, "repetition", True, "parola ripetuta")]


def test_repetition_across_a_long_pause_is_not_a_stutter():
    assert find_repetitions(make_words("bello. bello davvero", pauses={1: 1.5})) == []
