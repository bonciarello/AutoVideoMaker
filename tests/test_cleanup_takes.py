from cleanup_rules import Candidate, find_cue_takes, find_retakes, run_rules
from helpers import make_words

RETAKE = "stessa frase ripresa subito dopo"


def test_retake_that_extends_the_first_version_is_sure():
    words = make_words("Io credo che sia giusto. Io credo che sia giusto e utile.")
    assert find_retakes(words) == [Candidate(0, 4, "retake", True, RETAKE)]


def test_anaphora_is_only_dubious():
    words = make_words("Non è una questione di soldi. Non è una questione di tempo.")
    assert find_retakes(words) == [Candidate(0, 5, "retake", False, RETAKE)]


def test_interrupted_first_version_is_sure():
    words = make_words("Stanno correndo sempre più... Stanno correndo sempre di più.")
    assert find_retakes(words) == [Candidate(0, 3, "retake", True, RETAKE)]


def test_retake_chain_keeps_only_the_last_version():
    words = make_words("Il punto è. Il punto è che. Il punto è che funziona.")
    assert [(c.from_id, c.to_id) for c in find_retakes(words)] == [(0, 2), (3, 6)]


def test_different_sentences_are_not_retakes():
    assert find_retakes(make_words("Ciao a tutti. Oggi parliamo di IA.")) == []


def test_cue_word_with_matching_restart_is_sure():
    words = make_words("Il modello è stato allenato con i dati di rifaccio Il modello è stato addestrato",
                       pauses={9: 0.5, 10: 0.5})
    assert find_cue_takes(words, "rifaccio") == [
        Candidate(0, 9, "cue_word", True, "take segnato con «rifaccio»")]


def test_cue_word_includes_ok_before_it():
    words = make_words("Il modello è stato allenato male ok rifaccio Il modello è stato addestrato",
                       pauses={6: 0.5, 8: 0.5})
    found = find_cue_takes(words, "rifaccio")
    assert (found[0].from_id, found[0].to_id, found[0].sure) == (0, 7, True)


def test_cue_word_without_restart_cuts_previous_phrase_as_dubious():
    words = make_words("Prima frase. Questa cosa è importante. Ok rifaccio. Parliamo d'altro adesso",
                       pauses={6: 0.5, 8: 0.5})
    assert find_cue_takes(words, "rifaccio") == [
        Candidate(2, 7, "cue_word", False, "«rifaccio» senza ripartenza riconoscibile")]


def test_cue_word_inside_a_sentence_is_ignored():
    assert find_cue_takes(make_words("domani lo rifaccio con calma"), "rifaccio") == []


def test_cue_word_disabled():
    words = make_words("errore rifaccio errore giusto", pauses={1: 0.5, 2: 0.5})
    assert find_cue_takes(words, "") == []


def test_run_rules_combines_and_sorts():
    # «non è... Non è» è trovato sia come frase interrotta sia come gruppo ripetuto: un solo candidato
    words = make_words("Però non è... Non è il massimo. una delle delle aziende")
    assert [(c.from_id, c.to_id, c.kind) for c in run_rules(words, "rifaccio")] == [
        (1, 2, "false_start"), (8, 8, "repetition")]


def test_run_rules_without_words():
    assert run_rules([], "rifaccio") == []
