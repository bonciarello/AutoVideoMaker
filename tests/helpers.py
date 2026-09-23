"""Parole sintetiche per i test della pulizia take."""
from utils import normalize_word


def make_words(text, start=0.0, word_dur=0.3, gap=0.1, pauses=None):
    """
    Una parola per ogni token di `text`: ognuna dura `word_dur` secondi ed
    è separata dalla precedente da `gap` secondi.

    :param pauses: {indice_parola: pausa_prima_della_parola} per pause diverse
    """
    pauses = pauses or {}
    words = []
    t = start
    for i, token in enumerate(text.split()):
        if i > 0:
            t += pauses.get(i, gap)
        words.append({
            "id": i,
            "start": round(t, 3),
            "end": round(t + word_dur, 3),
            "word": normalize_word(token),
            "text": token,
            "confidence": 0.99,
        })
        t += word_dur
    return words
