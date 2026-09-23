#!/usr/bin/env python3
"""
Pulizia take — regole deterministiche.

Trova nelle parole trascritte i pezzi da togliere: take segnati con la
parola-segnale («rifaccio»), frasi interrotte con «...», parole ripetute di
fila e take ripetuti. Ogni candidato è "sicuro" (applicato senza revisione)
oppure "dubbio" (lo valuta Claude; senza Claude viene applicato con un
marcatore da rivedere in CapCut).

Le parole sono dict {"id", "start", "end", "word", "text", "confidence"}:
gli estremi dei candidati sono posizioni nella lista, inclusi.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from utils import normalize_word

# Soglie (da tarare sul banco di prova)
PHRASE_GAP = 0.6               # pausa (s) che chiude una frase
CUE_PAUSE = 0.3                # pausa minima (s) prima o dopo la parola-segnale
CUE_PREFIX_WORDS = frozenset({"ok", "okay", "no", "scusate", "scusa", "aspetta"})
CUE_PREFIX_MAX_GAP = 1.0       # distanza massima (s) delle parole di contorno
RETAKE_LOOKBACK = 60.0         # quanto indietro (s) cercare l'inizio del take rifatto
RESTART_MIN = 3                # parole minime della ripartenza da ritrovare
RESTART_MAX = 5
FALSE_START_MAX_SUFFIX = 5     # parole massime ripetute tra frammento e ripartenza
FALSE_START_MAX_FRAGMENT = 3   # frammento breve senza ripetizione: candidato dubbio
REPETITION_MAX_N = 3           # lunghezza massima del gruppo ripetuto
REPETITION_MAX_GAP = 1.0       # pausa massima (s) tra le due occorrenze
RETAKE_MIN_PREFIX = 3          # parole iniziali uguali per parlare di take ripetuto
RETAKE_MAX_DISTANCE = 20.0     # distanza massima (s) tra le due versioni
RETAKE_MAX_SECONDS = 30.0      # versione scartata più lunga di così: niente candidato

# Parole brevi la cui ripetizione è quasi sempre un inciampo
FUNCTION_WORDS = frozenset({
    # articoli
    "il", "lo", "la", "i", "gli", "le", "l", "un", "uno", "una",
    # preposizioni semplici e articolate
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra", "col",
    "del", "dello", "della", "dei", "degli", "delle", "dell",
    "al", "allo", "alla", "ai", "agli", "alle", "all",
    "dal", "dallo", "dalla", "dai", "dagli", "dalle", "dall",
    "nel", "nello", "nella", "nei", "negli", "nelle", "nell",
    "sul", "sullo", "sulla", "sui", "sugli", "sulle", "sull",
    # congiunzioni e connettivi
    "e", "ed", "o", "od", "ma", "che", "se", "perché", "anche", "come", "cioè", "quindi", "però",
    # pronomi atoni e negazione
    "mi", "ti", "ci", "vi", "si", "ne", "li", "non",
    # ausiliari brevi
    "è", "sono", "ho", "hai", "ha", "hanno", "abbiamo", "era", "sia",
    # dimostrativi
    "questo", "questa", "questi", "queste", "quel", "quello", "quella", "quelli", "quelle", "quei",
})

# Ripetizioni volute per enfasi: mai tagliate
EMPHATIC_WORDS = frozenset({"no", "sì", "piano", "via", "così", "quasi", "bene", "ora", "subito", "presto"})

# Etichette italiane per prompt, report e marcatori
KIND_LABELS = {
    "cue_word": "parola-segnale",
    "false_start": "falsa partenza",
    "self_correction": "autocorrezione",
    "repetition": "ripetizione",
    "retake": "take ripetuto",
}

_SENTENCE_END = ('.', '?', '!', '…')

Words = Sequence[Dict]


@dataclass
class Candidate:
    """Parole da togliere (da from_id a to_id, inclusi) con tipo, certezza e motivo."""
    from_id: int
    to_id: int
    kind: str
    sure: bool
    reason: str
    source: str = "rule"


def normalized(words: Words) -> List[str]:
    """Forma normalizzata di ogni parola, per i confronti."""
    return [normalize_word(w.get('word') or w.get('text', '')) for w in words]


def ends_with_ellipsis(text: str) -> bool:
    """True se la parola chiude una frase interrotta («a...», «verso…»)."""
    return (text or '').rstrip().endswith(('...', '…'))


def split_phrases(words: Words, phrase_gap: float = PHRASE_GAP) -> List[Tuple[int, int]]:
    """
    Divide le parole in frasi: una frase si chiude su . ? ! ... … oppure
    prima di una pausa più lunga di phrase_gap.

    :return: [(prima, ultima), ...] indici inclusivi, contigui e ordinati
    """
    phrases = []
    start = 0
    for i, w in enumerate(words):
        is_last = i == len(words) - 1
        closes = (w.get('text') or '').rstrip().endswith(_SENTENCE_END)
        if is_last or closes or words[i + 1]['start'] - w['end'] > phrase_gap:
            phrases.append((start, i))
            start = i + 1
    return phrases


def _phrase_start_index(phrases: List[Tuple[int, int]]) -> Dict[int, int]:
    """Per ogni parola, l'indice della prima parola della sua frase."""
    index = {}
    for s, e in phrases:
        for k in range(s, e + 1):
            index[k] = s
    return index


def find_false_starts(words: Words, norm: Optional[List[str]] = None,
                      phrases: Optional[List[Tuple[int, int]]] = None) -> List[Candidate]:
    """
    Frasi interrotte con «...» (Deepgram le segna così).

    Se la ripartenza ripete le ultime parole del frammento («non è... Non
    è il massimo») il taglio è sicuro; se riformula con parole diverse e il
    frammento è breve («Buongiorno a... Ciao a tutti») è dubbio; i frammenti
    lunghi riformulati restano a Claude.
    """
    norm = norm if norm is not None else normalized(words)
    phrases = phrases if phrases is not None else split_phrases(words)
    phrase_start = _phrase_start_index(phrases)
    found = []
    for k in range(len(words) - 1):
        if not ends_with_ellipsis(words[k].get('text', '')):
            continue
        start = phrase_start[k]
        max_j = min(FALSE_START_MAX_SUFFIX, k - start + 1, len(words) - k - 1)
        best_j = 0
        for j in range(max_j, 0, -1):
            fragment = norm[k - j + 1:k + 1]
            if all(fragment) and fragment == norm[k + 1:k + 1 + j]:
                best_j = j
                break
        if best_j:
            found.append(Candidate(k - best_j + 1, k, "false_start", True,
                                   "ripartenza con le stesse parole"))
        elif k - start + 1 <= FALSE_START_MAX_FRAGMENT:
            found.append(Candidate(start, k, "false_start", False,
                                   "frase interrotta e riformulata"))
    return found


def find_repetitions(words: Words, norm: Optional[List[str]] = None) -> List[Candidate]:
    """
    Parole (o gruppi fino a 3 parole) ripetute di fila: si toglie la prima
    occorrenza. Sicuro per gruppi e parole funzione, dubbio per le altre
    parole («molto molto») e per i gruppi chiusi da una virgola («è una
    hit, è una hit»); le ripetizioni enfatiche («no no») restano.
    """
    norm = norm if norm is not None else normalized(words)
    found = []
    i = 0
    while i < len(words):
        match = 0
        for n in range(REPETITION_MAX_N, 0, -1):
            if i + 2 * n > len(words):
                continue
            first, second = norm[i:i + n], norm[i + n:i + 2 * n]
            if not all(first) or first != second:
                continue
            if words[i + n]['start'] - words[i + n - 1]['end'] > REPETITION_MAX_GAP:
                continue
            # Una parola che chiude la frase («...di questo. Questo è...») non è
            # un inciampo: la ripetizione a cavallo di due frasi resta. «...» no:
            # è il segnale della falsa partenza.
            closing = (words[i + n - 1].get('text') or '').rstrip()
            if closing.endswith(('.', '?', '!')) and not ends_with_ellipsis(closing):
                continue
            if n == 1 and first[0] in EMPHATIC_WORDS:
                continue
            match = n
            break
        if not match:
            i += 1
            continue
        if match > 1:
            # Un gruppo chiuso da una virgola («è una hit, è una hit») può
            # essere enfasi voluta: lo decide Claude.
            after_comma = (words[i + match - 1].get('text') or '').rstrip().endswith(',')
            sure = not after_comma
            reason = "gruppo ripetuto dopo una virgola" if after_comma else "gruppo di parole ripetuto"
        else:
            sure = norm[i] in FUNCTION_WORDS
            reason = "parola ripetuta"
        found.append(Candidate(i, i + match - 1, "repetition", sure, reason))
        i += match
    return found


def find_retakes(words: Words, norm: Optional[List[str]] = None,
                 phrases: Optional[List[Tuple[int, int]]] = None) -> List[Candidate]:
    """
    Take ripetuti: due frasi di fila che iniziano con le stesse 3+ parole.
    Si toglie la prima versione; è sicuro solo se la prima è interrotta o
    è interamente l'inizio della seconda (altrimenti può essere un'anafora).
    """
    norm = norm if norm is not None else normalized(words)
    phrases = phrases if phrases is not None else split_phrases(words)
    found = []
    for (ps, pe), (qs, qe) in zip(phrases, phrases[1:]):
        if words[qs]['start'] - words[pe]['end'] > RETAKE_MAX_DISTANCE:
            continue
        if words[pe]['end'] - words[ps]['start'] > RETAKE_MAX_SECONDS:
            continue
        p, q = norm[ps:pe + 1], norm[qs:qe + 1]
        common = 0
        while common < len(p) and common < len(q) and p[common] and p[common] == q[common]:
            common += 1
        if common < RETAKE_MIN_PREFIX:
            continue
        sure = (ends_with_ellipsis(words[pe].get('text', ''))
                or (common == len(p) and len(q) >= len(p)))
        found.append(Candidate(ps, pe, "retake", sure, "stessa frase ripresa subito dopo"))
    return found


def _find_restart(norm: List[str], words: Words, before: int, restart: List[str]) -> Optional[int]:
    """
    Posizione (< before) da cui iniziano le stesse parole della ripartenza:
    prima si massimizza quante parole coincidono (da RESTART_MAX a
    RESTART_MIN), poi si prende la posizione più recente, entro
    RETAKE_LOOKBACK secondi.
    """
    if before <= 0 or len(restart) < RESTART_MIN:
        return None
    limit = words[before]['start'] - RETAKE_LOOKBACK
    for k in range(min(RESTART_MAX, len(restart)), RESTART_MIN - 1, -1):
        target = restart[:k]
        if not all(target):
            continue
        for s in range(before - k, -1, -1):
            if words[s]['start'] < limit:
                break
            if norm[s:s + k] == target:
                return s
    return None


def _phrase_start_before(phrases: List[Tuple[int, int]], index: int) -> int:
    """Inizio della frase che contiene la parola subito prima di index."""
    if index <= 0:
        return 0
    for s, e in phrases:
        if s <= index - 1 <= e:
            return s
    return index - 1


def find_cue_takes(words: Words, cue_word: str, norm: Optional[List[str]] = None,
                   phrases: Optional[List[Tuple[int, int]]] = None) -> List[Candidate]:
    """
    Take segnati a voce: la parola-segnale detta da sola (pausa prima o
    dopo) scarta il take appena sbagliato. Se le parole dopo la
    parola-segnale ricalcano parole dette poco prima, il taglio parte da lì
    ed è sicuro; altrimenti parte dall'inizio della frase precedente ed è
    dubbio. Le parole di contorno subito prima («ok rifaccio») sono incluse.
    """
    cue = normalize_word(cue_word or '')
    if not cue:
        return []
    norm = norm if norm is not None else normalized(words)
    phrases = phrases if phrases is not None else split_phrases(words)
    found = []
    for k, w in enumerate(words):
        if norm[k] != cue:
            continue
        gap_before = w['start'] - words[k - 1]['end'] if k > 0 else float('inf')
        gap_after = words[k + 1]['start'] - w['end'] if k + 1 < len(words) else float('inf')
        if gap_before < CUE_PAUSE and gap_after < CUE_PAUSE:
            continue
        first = k
        while (first > 0 and norm[first - 1] in CUE_PREFIX_WORDS
               and words[first]['start'] - words[first - 1]['end'] <= CUE_PREFIX_MAX_GAP):
            first -= 1
        start = _find_restart(norm, words, first, norm[k + 1:k + 1 + RESTART_MAX])
        if start is not None:
            found.append(Candidate(start, k, "cue_word", True, f"take segnato con «{cue_word}»"))
        else:
            found.append(Candidate(_phrase_start_before(phrases, first), k, "cue_word", False,
                                   f"«{cue_word}» senza ripartenza riconoscibile"))
    return found


def run_rules(words: Words, cue_word: str = "rifaccio") -> List[Candidate]:
    """
    Tutte le regole. Se più regole trovano lo stesso intervallo resta il
    primo candidato trovato, sicuro se almeno una regola lo considera tale.

    :return: candidati ordinati per (from_id, to_id)
    """
    if not words:
        return []
    norm = normalized(words)
    phrases = split_phrases(words)
    found = (find_cue_takes(words, cue_word, norm, phrases)
             + find_false_starts(words, norm, phrases)
             + find_repetitions(words, norm)
             + find_retakes(words, norm, phrases))
    unique: Dict[Tuple[int, int], Candidate] = {}
    for cand in found:
        key = (cand.from_id, cand.to_id)
        if key not in unique:
            unique[key] = cand
        elif cand.sure and not unique[key].sure:
            kept = unique[key]
            unique[key] = Candidate(kept.from_id, kept.to_id, kept.kind, True, kept.reason)
    return sorted(unique.values(), key=lambda c: (c.from_id, c.to_id))
