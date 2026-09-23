# Pulizia take — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AutoVideoMaker toglie in automatico, oltre alle pause, false partenze, autocorrezioni, parole ripetute, take ripetuti e take segnati con «rifaccio», e segnala in CapCut i tagli dubbi con un marcatore.

**Architecture:** Regole deterministiche (`cleanup_rules.py`) propongono candidati sicuri o dubbi sulle parole trascritte; Claude (`cleanup_llm.py`) giudica i dubbi e trova le riformulazioni, rispondendo solo con numeri di parola; `cleanup.py` applica la tabella degli esiti, converte le parole in tempi (punto più silenzioso nelle pause) e scrive il report. La pipeline esistente riceve i tagli tramite `ai_cuts` e i marcatori tramite un nuovo parametro `markers` verso l'export CapCut.

**Tech Stack:** Python 3.14 (venv), numpy, anthropic 0.120.2 (`client.beta.messages.create` con output strutturato), Deepgram SDK 7.6, pytest 9, ffmpeg.

**Spec:** `docs/superpowers/specs/2026-09-23-pulizia-take-design.md`

## Global Constraints

- Tutti i comandi si lanciano dalla root del repo: `/Users/bonciarello/Documents/GitHub/AutoVideoMaker`. Test: `venv/bin/python -m pytest`.
- Identificatori in inglese; commenti, messaggi in console, report e titoli dei marcatori in italiano; README in inglese.
- Tempi in secondi (float) in tutto il codice Python; microsecondi solo dentro `src/capcut_export.py`.
- Claude: modello `claude-opus-5` (costante `CLAUDE_MODEL` in `src/utils.py`), `client.beta.messages.create`, `max_tokens=16000`, `output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}}`, `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`, parametro `thinking` omesso (adattivo di default).
- Deepgram invariato: `nova-3`, lingua `it`, `smart_format=True`, `punctuate=True`.
- Soglie: `PHRASE_GAP` 0,6 s · `CUE_PAUSE` 0,3 s · `RETAKE_LOOKBACK` 60 s · `RETAKE_MAX_DISTANCE` 20 s · `RETAKE_MAX_SECONDS` 30 s · `WINDOW_WORDS` 1500 · `WINDOW_OVERLAP` 150 · `MAX_CUT_SECONDS` 30 · `MAX_WINDOW_FRACTION` 0,2 · `MARKER_TITLE_MAX` 60 · parola-segnale di default `rifaccio`.
- Mai sovrascrivere un progetto CapCut esistente. Mai committare dati del video dell'utente: `output/` resta ignorato e i dati di test si costruiscono in Python.
- Dipendenze: `anthropic>=0.120.2` in `requirements.txt`; `pytest` solo in `requirements-dev.txt`; nessun'altra nuova dipendenza.
- Ogni commit termina con la riga `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **Video senza parlato o con pochissime parole** (b-roll in un batch, clip muta): la pulizia deve restituire zero tagli senza chiamare Claude e senza errori in `split_phrases`/`make_windows`. Test: Task 4 `test_run_rules_without_words`, Task 5 `test_make_windows_without_words`, Task 7 `test_run_cleanup_without_words_returns_empty_and_skips_claude`.
2. **Rilancio su un video già elaborato** (video già spostato in `output/`, `words.json` presente, progetto CapCut esistente, chunk vecchi): trascrizione riusata, nuovo progetto `-2`, chunk vecchi rimossi. Test: Task 2 `test_words_json_is_reused_after_video_moves_to_output_folder`, Task 9 `test_generate_does_not_overwrite_existing_project`, Task 10 `test_clear_old_chunks_removes_only_chunk_files`.
3. **Timestamp sovrapposti** (fine di una parola dopo l'inizio della successiva, capita con Deepgram e Whisper): il taglio non deve invertirsi né entrare nelle parole tenute oltre ±30 ms. Test: Task 7 `test_cut_with_overlapping_timestamps_stays_within_30ms`.
4. **Tagli all'inizio o alla fine del video** e marcatore dopo l'ultimo segmento: tempi 0 / durata, marcatore a fine timeline. Test: Task 7 `test_cut_at_video_start_and_end`, Task 9 `test_marker_after_last_segment_goes_to_timeline_end`.
5. **Doppioni** tra blocchi Claude sovrapposti o tra regole diverse sullo stesso intervallo: un solo taglio, un solo marcatore. Test: Task 4 `test_run_rules_combines_and_sorts`, Task 7 `test_merge_applied_unions_duplicates_and_overlaps`.

---

### Task 0: Preparazione (passi manuali con l'utente)

**Files:** nessun file di codice.

**Interfaces:**
- Produces: branch `feature/pulizia-take`; `output/2026-09-16 09-10-23/banco-prova/capcut-manuale/draft_info.json`; `output/2026-09-16 09-10-23/banco-prova/auto-originale.edl`; il valore `MARKER_COLOR` usato nel Task 9.

- [ ] **Step 1: Far committare all'utente il lavoro in corso**

Run: `git status --short`
Expected: le modifiche dell'utente (`M main.py`, `?? src/capcut_export.py`, …) più `?? docs/`.

Chiedi all'utente di committare le sue modifiche, oppure di autorizzarti a farlo con un messaggio scelto da lui. Esempio, se autorizza:

```bash
git add .env.example README.md main.py requirements.txt run.sh src/
git commit -m "Export CapCut e tagli sulle parole"
```

Non procedere finché `git status --short` non mostra solo `?? docs/`.

- [ ] **Step 2: Creare il branch**

```bash
git switch -c feature/pulizia-take
```

- [ ] **Step 3: Committare spec e piano**

```bash
git add docs/superpowers
git commit -m "docs: spec e piano della pulizia take" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Mettere al sicuro il banco di prova**

```bash
BENCH="output/2026-09-16 09-10-23/banco-prova"
mkdir -p "$BENCH"
cp -R "$HOME/Movies/CapCut/User Data/Projects/com.lveditor.draft/2026-09-16 09-10-23" "$BENCH/capcut-manuale"
cp "output/2026-09-16 09-10-23/premiere_pro.edl" "$BENCH/auto-originale.edl"
python3 -c "import json;d=json.load(open('$BENCH/capcut-manuale/draft_info.json'));print(sum(len(t['segments']) for t in d['tracks'] if t['type']=='video'))"
```

Expected: stampa `206` (i segmenti del montaggio manuale).

- [ ] **Step 5: Ricavare il colore dei marcatori**

Chiedi all'utente: aprire in CapCut un progetto qualsiasi **diverso** da `2026-09-16 09-10-23`, aggiungere un marcatore, cambiargli colore (per esempio rosso), salvare e chiudere CapCut. Poi:

```bash
python3 - <<'EOF'
import glob, json, os
root = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
newest = max(glob.glob(os.path.join(root, "*/draft_info.json")), key=os.path.getmtime)
d = json.load(open(newest, encoding="utf-8"))
print(newest)
print(sorted({m["color"] for m in (d.get("time_marks") or {}).get("mark_items", [])}))
EOF
```

Expected: un elenco con il nuovo colore, per esempio `['#00c1cd', '#fe…']`. Annota il valore diverso da `#00c1cd`: è `MARKER_COLOR` nel Task 9. Se l'utente non può farlo, `MARKER_COLOR` resta `#00c1cd` (i marcatori si distinguono comunque dal titolo).

---

### Task 1: Infrastruttura dei test, `normalize_word` e aritmetica degli intervalli

**Files:**
- Create: `requirements-dev.txt`, `pytest.ini`, `tests/conftest.py`, `tests/helpers.py`, `tests/test_utils.py`, `src/intervals.py`, `tests/test_intervals.py`
- Modify: `.gitignore`, `src/utils.py`, `src/metadata_generation.py:17-18`, `requirements.txt`

**Interfaces:**
- Produces: `utils.CLAUDE_MODEL: str`; `utils.normalize_word(text: str) -> str`; `intervals.union(intervals) -> list[tuple[float, float]]`, `measure(intervals) -> float`, `complement(intervals, duration) -> list`, `intersect(a, b) -> list`, `subtract(a, b) -> list`; helper di test `helpers.make_words(text, start=0.0, word_dur=0.3, gap=0.1, pauses=None) -> list[dict]`.

- [ ] **Step 1: Preparare pytest**

`requirements-dev.txt`:

```
# Dipendenze di sviluppo (test)
pytest>=9.0
```

`pytest.ini`:

```ini
[pytest]
testpaths = tests
```

In `.gitignore`, subito dopo la riga `*.txt`, aggiungi:

```
!requirements-dev.txt
```

`tests/conftest.py`:

```python
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
```

`tests/helpers.py`:

```python
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
```

Run: `venv/bin/pip install -r requirements-dev.txt && git check-ignore requirements-dev.txt; echo "exit $?"`
Expected: pytest installato; `git check-ignore` non stampa il nome e termina con `exit 1` (file non ignorato).

- [ ] **Step 2: Scrivere i test che falliscono**

`tests/test_utils.py`:

```python
from utils import CLAUDE_MODEL, normalize_word


def test_normalize_word_strips_edge_punctuation_and_lowercases():
    assert normalize_word("Non") == "non"
    assert normalize_word("è...") == "è"
    assert normalize_word("tutti,") == "tutti"
    assert normalize_word("«Ciao»") == "ciao"


def test_normalize_word_keeps_inner_apostrophe():
    assert normalize_word("Dall'alto") == "dall'alto"
    assert normalize_word("dall\u2019alto") == "dall'alto"


def test_normalize_word_of_pure_punctuation_is_empty():
    assert normalize_word("...") == ""
    assert normalize_word("") == ""


def test_claude_model_is_opus_5():
    assert CLAUDE_MODEL == "claude-opus-5"
```

`tests/test_intervals.py`:

```python
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
```

- [ ] **Step 3: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_utils.py tests/test_intervals.py -v`
Expected: FAIL con `ImportError: cannot import name 'CLAUDE_MODEL'` e `ModuleNotFoundError: No module named 'intervals'`.

- [ ] **Step 4: Implementare**

In `src/utils.py` sostituisci il blocco degli import con:

```python
import json
import re
import subprocess
import unicodedata
from fractions import Fraction
from typing import Dict, Optional

# Modello Claude usato per metadati e pulizia take
CLAUDE_MODEL = 'claude-opus-5'

# Punteggiatura e simboli ai bordi di una parola
_EDGE_PUNCT_RE = re.compile(r"^[\W_]+|[\W_]+$")
```

e aggiungi in fondo al file:

```python
def normalize_word(text: str) -> str:
    """
    Forma normalizzata di una parola per i confronti: minuscolo, senza
    punteggiatura ai bordi. Gli apostrofi interni restano ("dall'alto").

    :param text: Parola così come trascritta (es. "Non", "è...", "«ciao»")
    :return: Parola normalizzata (es. "non", "è", "ciao"); stringa vuota se
             la parola è solo punteggiatura
    """
    t = unicodedata.normalize('NFC', text or '').lower().replace('\u2019', "'")
    return _EDGE_PUNCT_RE.sub('', t)
```

In `src/metadata_generation.py` sostituisci le righe 17-18:

```python
# Modello Anthropic per la generazione dei metadati testuali
CLAUDE_MODEL = 'claude-opus-5'
```

con:

```python
# Modello Anthropic per i metadati testuali (condiviso con la pulizia take)
from utils import CLAUDE_MODEL
```

In `requirements.txt` sostituisci `anthropic>=0.40.0` con `anthropic>=0.120.2`.

Crea `src/intervals.py`:

```python
#!/usr/bin/env python3
"""
Aritmetica di intervalli temporali [(start, end), ...] in secondi.
Usata dal report della pulizia take e dal banco di prova.
"""

from typing import List, Tuple

Interval = Tuple[float, float]


def union(intervals) -> List[Interval]:
    """Unisce intervalli sovrapposti o adiacenti; scarta quelli vuoti."""
    items = sorted((s, e) for s, e in intervals if e > s)
    merged: List[Interval] = []
    for s, e in items:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def measure(intervals) -> float:
    """Durata coperta dagli intervalli (le sovrapposizioni contano una volta)."""
    return sum(e - s for s, e in union(intervals))


def complement(intervals, duration: float) -> List[Interval]:
    """Parti di [0, duration] non coperte dagli intervalli."""
    out: List[Interval] = []
    pos = 0.0
    for s, e in union(intervals):
        s = min(max(s, 0.0), duration)
        e = min(e, duration)
        if s > pos:
            out.append((pos, s))
        pos = max(pos, e)
    if pos < duration:
        out.append((pos, duration))
    return out


def intersect(a, b) -> List[Interval]:
    """Intersezione di due insiemi di intervalli."""
    a, b = union(a), union(b)
    out: List[Interval] = []
    i = j = 0
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0])
        e = min(a[i][1], b[j][1])
        if e > s:
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract(a, b) -> List[Interval]:
    """Parti di a non coperte da b."""
    a = union(a)
    if not a:
        return []
    end = max(e for _, e in a)
    return intersect(a, complement(b, end))
```

- [ ] **Step 5: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_utils.py tests/test_intervals.py -v`
Expected: 11 PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt pytest.ini tests/conftest.py tests/helpers.py tests/test_utils.py tests/test_intervals.py src/utils.py src/intervals.py src/metadata_generation.py
git commit -m "test: infrastruttura pytest, normalize_word e intervalli" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Parole con id, testo e confidenza; `words.json`

**Files:**
- Modify: `src/transcription.py` (intero file, vedi sotto)
- Test: `tests/test_transcription_words.py`

**Interfaces:**
- Consumes: `utils.normalize_word`.
- Produces: parola = `{"id": int, "start": float, "end": float, "word": str, "text": str, "confidence": float}`; `transcription.deepgram_words(items) -> list[dict]`; `whisper_words(segments) -> list[dict]`; `transcribe_audio(...) -> {"text", "words", "transcriber", "model"}`; `save_words_json(path, transcription, video_path, video_duration, language) -> None`; `load_words_json(path, video_path, video_duration, transcriber, language) -> dict | None` (dict con `text`, `words`, `transcriber`, `model`).

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_transcription_words.py`:

```python
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
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_transcription_words.py -v`
Expected: FAIL con `ImportError: cannot import name 'deepgram_words'`.

- [ ] **Step 3: Implementare**

Sostituisci l'intero contenuto di `src/transcription.py` con:

```python
#!/usr/bin/env python3
"""
Flusso 4: Trascrizione Audio
Genera la trascrizione usando Deepgram (default) o Whisper AI.

Deepgram è il metodo di default: è veloce (API cloud) e non richiede
il download di modelli. Richiede DEEPGRAM_API_KEY nel file .env.
Se Deepgram non è configurato o fallisce, viene fatto fallback
automatico a Whisper (locale).

Ogni parola ha: id (posizione nella lista), start/end (secondi), word
(forma normalizzata), text (con punteggiatura, es. "a...") e confidence.
La trascrizione si salva in words.json e si riusa ai rilanci.
"""

import os
import json
from pathlib import Path
from typing import Optional

from utils import normalize_word

# Versione del formato di words.json
WORDS_FILE_VERSION = 1


def _with_ids(words: list) -> list:
    """Numera le parole in ordine: l'id è la posizione nella lista."""
    for i, w in enumerate(words):
        w['id'] = i
    return words


def deepgram_words(items) -> list:
    """
    Converte le parole della risposta Deepgram nel formato interno.

    :param items: Parole Deepgram (word, start, end e, se presenti,
           punctuated_word e confidence)
    :return: [{"id", "start", "end", "word", "text", "confidence"}, ...]
    """
    words = []
    for w in items or []:
        raw = getattr(w, 'word', None) or ''
        text = (getattr(w, 'punctuated_word', None) or raw).strip()
        if not text:
            continue
        words.append({
            'start': float(w.start),
            'end': float(w.end),
            'word': normalize_word(raw or text),
            'text': text,
            'confidence': float(getattr(w, 'confidence', None) or 0.0),
        })
    return _with_ids(words)


def whisper_words(segments) -> list:
    """
    Converte le parole dei segmenti Whisper nel formato interno
    (i token vuoti vengono scartati).
    """
    words = []
    for seg in segments or []:
        for w in seg.get('words', []):
            text = (w.get('word') or '').strip()
            if not text:
                continue
            words.append({
                'start': float(w['start']),
                'end': float(w['end']),
                'word': normalize_word(text),
                'text': text,
                'confidence': float(w.get('probability', 0.0)),
            })
    return _with_ids(words)


def transcribe_deepgram(audio_path: str,
                        language: str = "it",
                        model: str = "nova-3") -> dict:
    """
    Genera trascrizione usando Deepgram API, con timestamp a livello di parola.

    :param audio_path: Percorso del file audio (WAV)
    :param language: Lingua della trascrizione (default: it)
    :param model: Modello Deepgram (default: nova-3)
    :return: {"text": str, "words": [...]} (liste vuote se fallita)
    """
    # Carica .env per ottenere la chiave API
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv non disponibile, usa variabili d'ambiente del sistema

    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        print("DEEPGRAM_API_KEY non trovata nel file .env.")
        return {"text": "", "words": []}

    try:
        from deepgram import DeepgramClient
    except ImportError:
        print("deepgram-sdk non installato. Installalo con: pip install deepgram-sdk")
        return {"text": "", "words": []}

    try:
        print(f"Generando trascrizione con Deepgram ({model})...")
        client = DeepgramClient(api_key=api_key)

        with open(audio_path, 'rb') as audio_file:
            buffer_data = audio_file.read()

        # API deepgram-sdk >= 5.x
        response = client.listen.v1.media.transcribe_file(
            request=buffer_data,
            model=model,
            language=language,
            smart_format=True,
            punctuate=True
        )

        alternative = response.results.channels[0].alternatives[0]
        text = alternative.transcript.strip()

        # Parole con timestamp e punteggiatura (i «...» servono alla pulizia take)
        words = deepgram_words(alternative.words)

        print(f"   ({len(words)} parole rilevate)")
        return {"text": text, "words": words}

    except Exception as e:
        print(f"Errore durante la trascrizione Deepgram: {e}")
        return {"text": "", "words": []}


def transcribe_whisper(audio_path: str,
                       model_size: str = "medium",
                       language: str = "it") -> dict:
    """
    Genera trascrizione usando Whisper, con timestamp a livello di parola.

    :param audio_path: Percorso del file audio (WAV)
    :param model_size: Dimensione del modello Whisper (tiny, base, small, medium, large)
    :param language: Lingua della trascrizione (default: it)
    :return: {"text": str, "words": [...]} (liste vuote se fallita)
    """
    try:
        import whisper
    except ImportError:
        print("ATTENZIONE: openai-whisper non è installato. Installalo con: pip install openai-whisper")
        return {"text": "", "words": []}

    try:
        print(f"Generando trascrizione con Whisper {model_size}...")
        model = whisper.load_model(model_size)
        result = model.transcribe(audio_path, language=language, word_timestamps=True)

        text = result['text'].strip()
        words = whisper_words(result.get('segments', []))

        print(f"   ({len(words)} parole rilevate)")
        return {"text": text, "words": words}
    except Exception as e:
        print(f"Errore durante la trascrizione Whisper: {e}")
        return {"text": "", "words": []}


def transcribe_audio(audio_path: str,
                     transcriber: str = "deepgram",
                     whisper_model: str = "medium",
                     deepgram_model: str = "nova-3",
                     language: str = "it") -> dict:
    """
    Genera la trascrizione dell'audio con il servizio richiesto.

    Deepgram è il metodo di default. Se Deepgram non è configurato o
    fallisce, viene fatto fallback automatico a Whisper.

    :return: {"text", "words", "transcriber", "model"}: transcriber e model
             sono quelli effettivamente usati (dopo un eventuale fallback)
    """
    if transcriber == "deepgram":
        result = transcribe_deepgram(audio_path, language=language, model=deepgram_model)
        if result["text"]:
            return {**result, "transcriber": "deepgram", "model": deepgram_model}
        print("   Fallback a Whisper...")

    result = transcribe_whisper(audio_path, model_size=whisper_model, language=language)
    return {**result, "transcriber": "whisper", "model": whisper_model}


def save_words_json(path: str, transcription: dict, video_path: str,
                    video_duration: float, language: str) -> None:
    """
    Salva testo e parole in words.json, con i dati per riconoscere il video
    (nome, dimensione, durata) e le opzioni usate.
    """
    data = {
        'version': WORDS_FILE_VERSION,
        'video': {
            'name': Path(video_path).name,
            'size': os.path.getsize(video_path),
            'duration': round(video_duration, 3),
        },
        'transcriber': transcription.get('transcriber'),
        'model': transcription.get('model'),
        'language': language,
        'text': transcription.get('text', ''),
        'words': transcription.get('words', []),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def load_words_json(path: str, video_path: str, video_duration: float,
                    transcriber: str, language: str) -> Optional[dict]:
    """
    Riusa words.json se appartiene a questo video (nome, dimensione, durata
    entro 0,1 s) ed è stato fatto con lo stesso servizio e la stessa lingua.

    :return: {"text", "words", "transcriber", "model"} oppure None (file
             mancante, illeggibile o di un altro video/opzioni)
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        video = data['video']
        matches = (
            data.get('version') == WORDS_FILE_VERSION
            and video['name'] == Path(video_path).name
            and video['size'] == os.path.getsize(video_path)
            and abs(float(video['duration']) - video_duration) <= 0.1
            and data['language'] == language
            and data['transcriber'] == transcriber
        )
        if not matches:
            return None
        return {'text': data.get('text', ''), 'words': data['words'],
                'transcriber': data['transcriber'], 'model': data.get('model')}
    except (OSError, ValueError, KeyError, TypeError):
        return None


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python transcription.py <audio_path> [deepgram|whisper]")
        sys.exit(1)

    audio = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else "deepgram"
    result = transcribe_audio(audio, transcriber=method)
    text = result["text"]
    print(f"\nTrascrizione ({len(text)} caratteri, {len(result['words'])} parole):")
    print(text[:500] + ("..." if len(text) > 500 else ""))
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_transcription_words.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/transcription.py tests/test_transcription_words.py
git commit -m "feat: parole con punteggiatura e riuso di words.json" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Regole — frasi, frasi interrotte, parole ripetute

**Files:**
- Create: `src/cleanup_rules.py`
- Test: `tests/test_cleanup_rules.py`

**Interfaces:**
- Consumes: `utils.normalize_word`, `helpers.make_words`.
- Produces: `cleanup_rules.Candidate(from_id: int, to_id: int, kind: str, sure: bool, reason: str, source: str = "rule")` (dataclass, estremi inclusi); `KIND_LABELS: dict[str, str]`; `normalized(words) -> list[str]`; `ends_with_ellipsis(text) -> bool`; `split_phrases(words, phrase_gap=PHRASE_GAP) -> list[tuple[int, int]]`; `find_false_starts(words, norm=None, phrases=None) -> list[Candidate]`; `find_repetitions(words, norm=None) -> list[Candidate]`; costanti delle soglie.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_cleanup_rules.py`:

```python
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
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_cleanup_rules.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'cleanup_rules'`.

- [ ] **Step 3: Implementare**

Crea `src/cleanup_rules.py`:

```python
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
    "cue_word": "rifaccio",
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
    parole («molto molto»); le ripetizioni enfatiche («no no») restano.
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
            if n == 1 and first[0] in EMPHATIC_WORDS:
                continue
            match = n
            break
        if not match:
            i += 1
            continue
        sure = match > 1 or norm[i] in FUNCTION_WORDS
        reason = "gruppo di parole ripetuto" if match > 1 else "parola ripetuta"
        found.append(Candidate(i, i + match - 1, "repetition", sure, reason))
        i += match
    return found
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_cleanup_rules.py -v`
Expected: 13 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cleanup_rules.py tests/test_cleanup_rules.py
git commit -m "feat: regole per frasi interrotte e parole ripetute" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Regole — take ripetuti, «rifaccio» e `run_rules`

**Files:**
- Modify: `src/cleanup_rules.py` (aggiunte in fondo)
- Test: `tests/test_cleanup_takes.py`

**Interfaces:**
- Consumes: tutto ciò che produce il Task 3.
- Produces: `find_retakes(words, norm=None, phrases=None) -> list[Candidate]`; `find_cue_takes(words, cue_word, norm=None, phrases=None) -> list[Candidate]`; `run_rules(words, cue_word="rifaccio") -> list[Candidate]` (ordinati per `(from_id, to_id)`, senza doppioni).

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_cleanup_takes.py`:

```python
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
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_cleanup_takes.py -v`
Expected: FAIL con `ImportError: cannot import name 'find_cue_takes'`.

- [ ] **Step 3: Implementare**

Aggiungi in fondo a `src/cleanup_rules.py`:

```python
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
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_cleanup_rules.py tests/test_cleanup_takes.py -v`
Expected: 25 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cleanup_rules.py tests/test_cleanup_takes.py
git commit -m "feat: regole per take ripetuti e parola-segnale" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Passata Claude — blocchi, testo del blocco, schema e validazione

**Files:**
- Create: `src/cleanup_llm.py`
- Test: `tests/test_cleanup_llm.py`

**Interfaces:**
- Consumes: `cleanup_rules.Candidate`, `KIND_LABELS`, `split_phrases`; `utils.CLAUDE_MODEL`.
- Produces: `WindowRejected(Exception)`; `make_windows(phrases, n_words, window_words=WINDOW_WORDS, overlap=WINDOW_OVERLAP) -> list[tuple[int, int]]`; `assign_candidates(windows, numbered) -> dict[int, list[tuple[int, Candidate]]]`; `format_window(words, window, index, total, numbered) -> str`; `SYSTEM_PROMPT: str`; `OUTPUT_SCHEMA: dict`; `validate_response(data, words, window, numbered) -> (dict[int, tuple[bool, bool]], list[Candidate], list[str])`; costanti `WINDOW_WORDS`, `WINDOW_OVERLAP`, `MAX_WORKERS`, `MAX_CUT_SECONDS`, `MAX_WINDOW_FRACTION`, `PAUSE_MARK`, `MAX_TOKENS`, `FALLBACK_BETA`.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_cleanup_llm.py`:

```python
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
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_cleanup_llm.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'cleanup_llm'`.

- [ ] **Step 3: Implementare**

Crea `src/cleanup_llm.py`:

```python
#!/usr/bin/env python3
"""
Pulizia take — passata con Claude.

Claude riceve la trascrizione a blocchi, con ogni parola numerata, e i
candidati dubbi trovati dalle regole. Risponde in un formato JSON fisso:
un verdetto (taglia/tieni) per ogni candidato e i tagli nuovi, sempre come
numeri di parola. I tempi li calcola cleanup.py, mai l'LLM.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import anthropic

from cleanup_rules import KIND_LABELS, Candidate, split_phrases
from utils import CLAUDE_MODEL

WINDOW_WORDS = 1500          # parole per blocco
WINDOW_OVERLAP = 150         # parole di contesto condivise tra blocchi vicini
MAX_WORKERS = 3              # blocchi elaborati in parallelo
MAX_CUT_SECONDS = 30.0       # taglio singolo più lungo di così: scartato
MAX_WINDOW_FRACTION = 0.2    # oltre questa quota di parole tolte il blocco è scartato
PAUSE_MARK = 1.0             # pause (s) segnate nel testo inviato a Claude
MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

Numbered = List[Tuple[int, Candidate]]


class WindowRejected(Exception):
    """Risposta di Claude inutilizzabile per un blocco: per quel blocco restano le regole."""


SYSTEM_PROMPT = """Sei l'assistente di montaggio di un creator italiano. Ricevi un blocco della trascrizione di un video YouTube registrato di getto: ogni parola è preceduta dal suo numero (123:parola) e le pause lunghe sono segnate tra parentesi quadre.

Il tuo compito è solo ripulire il parlato. Da togliere:
- false partenze: frasi o parole iniziate e subito interrotte («Buongiorno a... Ciao a tutti»);
- autocorrezioni: un pezzo detto e subito riformulato («dall'alto verso... dal basso verso l'alto»): togli la versione scartata;
- take ripetuti: la stessa frase detta più volte; tieni l'ultima versione completa;
- parole ripetute per inciampo («delle delle», «che che»).

Da non togliere mai:
- contenuto detto una sola volta, anche se è una digressione o ti sembra debole;
- ripetizioni volute per enfasi e anafore retoriche («non è una questione di soldi, non è una questione di tempo»);
- parole che servono perché la frase che resta sia completa e scorrevole.
Non riscrivere e non riassumere: indichi solo cosa togliere.

Per ogni candidato dubbio elencato in fondo al blocco decidi se tagliarlo (cut: true) o tenerlo (cut: false).
I tagli nuovi li indichi con il numero della prima e dell'ultima parola da togliere, estremi inclusi.
Metti sure: false quando non sei certo che il taglio sia giusto: verrà segnalato all'autore per un controllo.
Il motivo (reason) è brevissimo, al massimo 8 parole, in italiano.
Se nel blocco non c'è niente da togliere, restituisci liste vuote."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "integer"},
                    "cut": {"type": "boolean"},
                    "sure": {"type": "boolean"},
                },
                "required": ["candidate", "cut", "sure"],
                "additionalProperties": False,
            },
        },
        "cuts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_id": {"type": "integer"},
                    "to_id": {"type": "integer"},
                    "kind": {"type": "string",
                             "enum": ["false_start", "self_correction", "retake", "repetition"]},
                    "sure": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["from_id", "to_id", "kind", "sure", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdicts", "cuts"],
    "additionalProperties": False,
}


def make_windows(phrases: List[Tuple[int, int]], n_words: int,
                 window_words: int = WINDOW_WORDS, overlap: int = WINDOW_OVERLAP) -> List[Tuple[int, int]]:
    """
    Divide la trascrizione in blocchi spezzati a fine frase. Ogni blocco
    dopo il primo riparte dalle frasi che coprono circa le ultime `overlap`
    parole del precedente, così Claude ha contesto ai confini.

    :param phrases: frasi [(prima, ultima), ...] da split_phrases
    :return: [(prima parola, ultima parola), ...] inclusivi
    """
    if n_words == 0 or not phrases:
        return []
    windows = []
    first_phrase = 0
    while True:
        first = phrases[first_phrase][0]
        last_phrase = first_phrase
        while (last_phrase + 1 < len(phrases)
               and phrases[last_phrase + 1][1] - first + 1 <= window_words):
            last_phrase += 1
        windows.append((first, phrases[last_phrase][1]))
        if last_phrase == len(phrases) - 1:
            return windows
        next_phrase = last_phrase + 1
        while (next_phrase - 1 > first_phrase
               and phrases[last_phrase][1] - phrases[next_phrase - 1][0] + 1 <= overlap):
            next_phrase -= 1
        first_phrase = next_phrase


def assign_candidates(windows: List[Tuple[int, int]], numbered: Numbered) -> Dict[int, Numbered]:
    """
    Ogni candidato va al primo blocco che lo contiene per intero; se nessun
    blocco lo contiene resta senza verdetto.
    """
    assigned: Dict[int, Numbered] = {}
    for num, cand in numbered:
        for idx, (first, last) in enumerate(windows):
            if first <= cand.from_id and cand.to_id <= last:
                assigned.setdefault(idx, []).append((num, cand))
                break
    return assigned


def format_window(words, window: Tuple[int, int], index: int, total: int, numbered: Numbered) -> str:
    """Testo del blocco per Claude: parole numerate, pause lunghe e candidati dubbi."""
    first, last = window
    tokens = []
    for i in range(first, last + 1):
        if i > first:
            gap = words[i]['start'] - words[i - 1]['end']
            if gap > PAUSE_MARK:
                tokens.append(f"[pausa {gap:.1f} s]".replace(".", ","))
        tokens.append(f"{i}:{words[i]['text']}")
    lines = [f"Blocco {index}/{total} · parole {first}–{last}", " ".join(tokens)]
    if numbered:
        lines += ["", "Candidati dubbi da valutare:"]
        for num, cand in numbered:
            text = " ".join(w['text'] for w in words[cand.from_id:cand.to_id + 1])
            label = KIND_LABELS.get(cand.kind, cand.kind)
            lines.append(f"C{num}: parole {cand.from_id}–{cand.to_id} · {label} · «{text}»")
    return "\n".join(lines)


def validate_response(data: dict, words, window: Tuple[int, int], numbered: Numbered):
    """
    Controlla la risposta di Claude per un blocco.

    :return: (verdetti {numero: (cut, sure)}, tagli nuovi [Candidate], avvisi)
    :raises WindowRejected: se Claude vuole togliere più di MAX_WINDOW_FRACTION del blocco
    """
    first, last = window
    by_number = dict(numbered)
    warnings = []
    verdicts = {}
    for v in data["verdicts"]:
        if v["candidate"] in by_number:
            verdicts[v["candidate"]] = (bool(v["cut"]), bool(v["sure"]))
    cuts = []
    for c in data["cuts"]:
        a, b = int(c["from_id"]), int(c["to_id"])
        if not first <= a <= b <= last:
            warnings.append(f"taglio fuori dal blocco ignorato (parole {a}–{b})")
            continue
        if words[b]['end'] - words[a]['start'] > MAX_CUT_SECONDS:
            warnings.append(f"taglio più lungo di {MAX_CUT_SECONDS:.0f} s ignorato (parole {a}–{b})")
            continue
        cuts.append(Candidate(a, b, c["kind"], bool(c["sure"]), c["reason"], source="claude"))
    removed = set()
    for cand in cuts:
        removed.update(range(cand.from_id, cand.to_id + 1))
    for num, (cut, _) in verdicts.items():
        if cut:
            cand = by_number[num]
            removed.update(range(cand.from_id, cand.to_id + 1))
    size = last - first + 1
    if len(removed) > MAX_WINDOW_FRACTION * size:
        raise WindowRejected(f"Claude voleva togliere il {100 * len(removed) / size:.0f}% del blocco")
    return verdicts, cuts, warnings
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_cleanup_llm.py -v`
Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cleanup_llm.py tests/test_cleanup_llm.py
git commit -m "feat: blocchi, prompt e validazione per la passata Claude" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Passata Claude — chiamata, parallelismo ed errori

**Files:**
- Modify: `src/cleanup_llm.py` (aggiunte in fondo)
- Test: `tests/test_cleanup_llm_calls.py`

**Interfaces:**
- Consumes: tutto ciò che produce il Task 5.
- Produces: `make_client() -> anthropic.Anthropic | None`; `ask_claude(client, user_text: str) -> dict`; `LlmResult(verdicts: dict[int, tuple[bool, bool]], cuts: list[Candidate], warnings: list[str], failed_windows: int)` (dataclass con default); `review_with_claude(words, dubious: list[Candidate], client, max_workers=MAX_WORKERS) -> LlmResult`. I candidati sono numerati da 1 nell'ordine di `dubious`.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_cleanup_llm_calls.py`:

```python
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from cleanup_llm import FALLBACK_BETA, WindowRejected, ask_claude, review_with_claude
from cleanup_rules import Candidate
from helpers import make_words


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeClient:
    def __init__(self, replies):
        self.beta = SimpleNamespace(messages=FakeMessages(replies))


def _reply(data, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason,
                           content=[SimpleNamespace(type="text", text=json.dumps(data))])


def test_ask_claude_sends_structured_output_request_with_fallback():
    client = FakeClient([_reply({"verdicts": [], "cuts": []})])
    assert ask_claude(client, "testo del blocco") == {"verdicts": [], "cuts": []}
    call = client.beta.messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["max_tokens"] == 16000
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["betas"] == [FALLBACK_BETA]
    assert call["fallbacks"] == "default"
    assert call["messages"] == [{"role": "user", "content": "testo del blocco"}]
    assert "thinking" not in call


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_ask_claude_rejects_refusal_and_truncation(reason):
    with pytest.raises(WindowRejected):
        ask_claude(FakeClient([_reply({}, stop_reason=reason)]), "x")


def test_review_maps_verdicts_and_new_cuts():
    words = make_words("una delle delle aziende. " + "parola " * 20 + "È molto molto bello.")
    dubious = [Candidate(25, 25, "repetition", False, "parola ripetuta")]
    client = FakeClient([_reply({
        "verdicts": [{"candidate": 1, "cut": True, "sure": True}],
        "cuts": [{"from_id": 1, "to_id": 1, "kind": "repetition", "sure": True, "reason": "inciampo"}]})])
    result = review_with_claude(words, dubious, client)
    assert result.verdicts == {1: (True, True)}
    assert result.cuts == [Candidate(1, 1, "repetition", True, "inciampo", source="claude")]
    assert result.failed_windows == 0
    assert "C1: parole 25–25" in client.beta.messages.calls[0]["messages"][0]["content"]


def test_review_survives_api_errors():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    client = FakeClient([anthropic.APIConnectionError(request=request)])
    result = review_with_claude(make_words("ciao a tutti"), [], client)
    assert result.failed_windows == 1
    assert result.cuts == []
    assert "senza Claude" in result.warnings[0]


def test_review_survives_malformed_response():
    client = FakeClient([_reply({"verdicts": [], "cuts": [{"from_id": 1}]})])
    result = review_with_claude(make_words("ciao a tutti"), [], client)
    assert result.failed_windows == 1
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_cleanup_llm_calls.py -v`
Expected: FAIL con `ImportError: cannot import name 'ask_claude'`.

- [ ] **Step 3: Implementare**

Aggiungi in fondo a `src/cleanup_llm.py`:

```python
def make_client():
    """Client Anthropic se ANTHROPIC_API_KEY è configurata (anche da .env), altrimenti None."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv non disponibile, usa le variabili d'ambiente del sistema
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic()


def ask_claude(client, user_text: str) -> dict:
    """
    Una richiesta a Claude con output strutturato (OUTPUT_SCHEMA) e
    fallback server-side in caso di rifiuto.

    :raises WindowRejected: risposta interrotta, rifiutata o senza JSON valido
    """
    response = client.beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_text}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise WindowRejected(f"risposta interrotta (stop_reason: {response.stop_reason})")
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    if not text:
        raise WindowRejected("risposta senza testo")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise WindowRejected(f"JSON non valido: {e}") from e


@dataclass
class LlmResult:
    """Esito della passata con Claude su tutti i blocchi."""
    verdicts: Dict[int, Tuple[bool, bool]] = field(default_factory=dict)
    cuts: List[Candidate] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    failed_windows: int = 0


def review_with_claude(words, dubious: List[Candidate], client, max_workers: int = MAX_WORKERS) -> LlmResult:
    """
    Manda a Claude tutti i blocchi, in parallelo, con i candidati dubbi.

    I candidati sono numerati da 1 nell'ordine di `dubious`: chi legge i
    verdetti deve usare lo stesso ordine. Un blocco che fallisce non ferma
    gli altri: i suoi candidati restano senza verdetto.
    """
    windows = make_windows(split_phrases(words), len(words))
    numbered = list(enumerate(dubious, start=1))
    assigned = assign_candidates(windows, numbered)

    def work(idx):
        user_text = format_window(words, windows[idx], idx + 1, len(windows), assigned.get(idx, []))
        return validate_response(ask_claude(client, user_text), words, windows[idx], assigned.get(idx, []))

    outcomes, errors = {}, {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(work, idx): idx for idx in range(len(windows))}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                outcomes[idx] = future.result()
            except (anthropic.APIError, WindowRejected, KeyError, TypeError, ValueError) as e:
                errors[idx] = e

    result = LlmResult()
    for idx in range(len(windows)):
        label = f"blocco {idx + 1}/{len(windows)}"
        if idx in errors:
            result.failed_windows += 1
            result.warnings.append(f"{label} senza Claude: {errors[idx]}")
            continue
        verdicts, cuts, warnings = outcomes[idx]
        result.verdicts.update(verdicts)
        result.cuts.extend(cuts)
        result.warnings.extend(f"{label}: {w}" for w in warnings)
    result.cuts.sort(key=lambda c: (c.from_id, c.to_id))
    return result
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_cleanup_llm.py tests/test_cleanup_llm_calls.py -v`
Expected: 16 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cleanup_llm.py tests/test_cleanup_llm_calls.py
git commit -m "feat: chiamata a Claude con output strutturato e fallback" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Orchestrazione — esiti, unione, dalle parole ai tempi

**Files:**
- Create: `src/cleanup.py`
- Test: `tests/test_cleanup.py`

**Interfaces:**
- Consumes: `cleanup_rules.run_rules`, `Candidate`, `KIND_LABELS`; `cleanup_llm.review_with_claude`, `LlmResult`.
- Produces: `Energy(rms: np.ndarray, frame_seconds=RMS_FRAME)` con `Energy.from_wav(path)` e `.quietest(lo, hi) -> float`; `cut_start_time(words, a, pad, energy) -> float`; `cut_end_time(words, b, pad, energy, video_duration) -> float`; `resolve_outcomes(rule_cands, dubious, llm) -> (list[tuple[Candidate, bool]], list[Candidate])`; `merge_applied(applied) -> list[dict]` (chiavi `from_id`, `to_id`, `parts`); `words_text(words, a, b) -> str`; `marker_title(kind, text) -> str`; `CleanupCut(from_id, to_id, kind, sure, source, reason, text, start, end, timeline_time=None)`; `CleanupResult(mode, cuts=[], kept=[], warnings=[])` con `.time_cuts() -> list[tuple[float, float]]` e `.markers() -> list[{"source_time": float, "title": str}]`; `run_cleanup(words, mode, cue_word, audio_path, video_duration, pad, client=None) -> CleanupResult`; `source_to_timeline(t, keep_ranges) -> float`.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_cleanup.py`:

```python
import numpy as np

from cleanup import (Energy, cut_end_time, cut_start_time, marker_title,
                     merge_applied, resolve_outcomes, run_cleanup,
                     source_to_timeline)
from cleanup_llm import LlmResult
from cleanup_rules import Candidate
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


def test_run_cleanup_without_words_returns_empty_and_skips_claude():
    class Boom:
        @property
        def beta(self):
            raise AssertionError("Claude non deve essere chiamato")

    result = run_cleanup([], mode="full", cue_word="rifaccio", audio_path=None,
                         video_duration=5.0, pad=0.05, client=Boom())
    assert result.cuts == [] and result.kept == []
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_cleanup.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'cleanup'`.

- [ ] **Step 3: Implementare**

Crea `src/cleanup.py`:

```python
#!/usr/bin/env python3
"""
Pulizia take — orchestrazione.

Regole deterministiche + Claude → tabella degli esiti → unione dei tagli a
livello di parola → tempi (punto più silenzioso nelle pause) → tagli per
process_and_export, marcatori per CapCut e report pulizia.md / pulizia.json.
"""

import json
import math
import os
import wave
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from cleanup_llm import LlmResult, review_with_claude
from cleanup_rules import KIND_LABELS, Candidate, run_rules
from intervals import measure

TOUCH_GAP = 0.02        # pausa (s) sotto la quale due parole sono "attaccate"
TOUCH_WINDOW = 0.03     # ricerca (s) attorno al confine tra parole attaccate
RMS_FRAME = 0.01        # finestra (s) dell'energia audio
MIN_CUT = 0.02          # taglio più corto di così: ignorato
MARKER_TITLE_MAX = 60   # caratteri massimi del titolo di un marcatore
CONTEXT_WORDS = 5       # parole di contesto nel report

SOURCE_LABELS = {"rule": "regola", "claude": "Claude", "claude+rule": "regola + Claude"}


class Energy:
    """Energia (RMS) dell'audio su finestre da 10 ms, per scegliere dove tagliare."""

    def __init__(self, rms: np.ndarray, frame_seconds: float = RMS_FRAME):
        self.rms = rms
        self.frame_seconds = frame_seconds

    @classmethod
    def from_wav(cls, path: str) -> "Energy":
        """Legge un WAV PCM a 16 bit (l'audio di analisi a 16 kHz mono)."""
        with wave.open(path, 'rb') as wf:
            rate = wf.getframerate()
            channels = wf.getnchannels()
            if wf.getsampwidth() != 2:
                raise ValueError("serve un WAV PCM a 16 bit")
            data = wf.readframes(wf.getnframes())
        samples = np.frombuffer(data, dtype='<i2').astype(np.float32)
        if channels > 1:
            samples = samples[:len(samples) // channels * channels].reshape(-1, channels).mean(axis=1)
        hop = max(1, int(round(rate * RMS_FRAME)))
        n = len(samples) // hop
        if n == 0:
            return cls(np.zeros(0, dtype=np.float32), hop / rate)
        frames = samples[:n * hop].reshape(n, hop)
        return cls(np.sqrt((frames ** 2).mean(axis=1)), hop / rate)

    def quietest(self, lo: float, hi: float) -> float:
        """Istante più silenzioso in [lo, hi]; il punto medio se non ci sono dati."""
        if hi < lo:
            lo, hi = hi, lo
        i0 = max(int(math.floor(lo / self.frame_seconds)), 0)
        i1 = min(int(math.ceil(hi / self.frame_seconds)), len(self.rms))
        if i1 <= i0:
            return (lo + hi) / 2
        k = i0 + int(np.argmin(self.rms[i0:i1]))
        return min(max((k + 0.5) * self.frame_seconds, lo), hi)


def _quietest(energy: Optional[Energy], lo: float, hi: float) -> float:
    """Punto più silenzioso, o il punto medio senza audio di analisi."""
    return energy.quietest(lo, hi) if energy is not None else (lo + hi) / 2


def cut_start_time(words, a: int, pad: float, energy: Optional[Energy]) -> float:
    """
    Inizio del taglio che toglie la parola a: nella pausa prima di a,
    lasciando `pad` dopo l'ultima parola tenuta quando la pausa lo permette.
    """
    if a == 0:
        return 0.0
    prev_end, start = words[a - 1]['end'], words[a]['start']
    gap = start - prev_end
    if gap >= 2 * pad:
        return _quietest(energy, prev_end + pad, start)
    if gap >= TOUCH_GAP:
        return _quietest(energy, prev_end, start)
    mid = (prev_end + start) / 2
    return _quietest(energy, mid - TOUCH_WINDOW, mid + TOUCH_WINDOW)


def cut_end_time(words, b: int, pad: float, energy: Optional[Energy], video_duration: float) -> float:
    """
    Fine del taglio che toglie la parola b: nella pausa dopo b, lasciando
    `pad` prima della parola tenuta successiva quando la pausa lo permette.
    """
    if b == len(words) - 1:
        return video_duration
    end, next_start = words[b]['end'], words[b + 1]['start']
    gap = next_start - end
    if gap >= 2 * pad:
        return _quietest(energy, end, next_start - pad)
    if gap >= TOUCH_GAP:
        return _quietest(energy, end, next_start)
    mid = (end + next_start) / 2
    return _quietest(energy, mid - TOUCH_WINDOW, mid + TOUCH_WINDOW)


def resolve_outcomes(rule_cands: List[Candidate], dubious: List[Candidate],
                     llm: Optional[LlmResult]) -> Tuple[List[Tuple[Candidate, bool]], List[Candidate]]:
    """
    Tabella degli esiti della spec.

    :param dubious: i candidati dubbi nello stesso ordine usato per numerarli con Claude
    :return: (tagli applicati come (candidato, serve_marcatore), candidati tenuti da Claude)
    """
    applied = [(c, False) for c in rule_cands if c.sure]
    kept = []
    for num, cand in enumerate(dubious, start=1):
        verdict = llm.verdicts.get(num) if llm else None
        if verdict is None:
            applied.append((cand, True))
        elif verdict[0]:
            applied.append((cand, not verdict[1]))
        else:
            kept.append(cand)
    if llm:
        applied.extend((c, not c.sure) for c in llm.cuts)
    return applied, kept


def merge_applied(applied: List[Tuple[Candidate, bool]]) -> List[Dict]:
    """Unisce i tagli sovrapposti o adiacenti a livello di parola."""
    groups: List[Dict] = []
    for cand, marker in sorted(applied, key=lambda item: (item[0].from_id, item[0].to_id)):
        if groups and cand.from_id <= groups[-1]["to_id"] + 1:
            groups[-1]["to_id"] = max(groups[-1]["to_id"], cand.to_id)
            groups[-1]["parts"].append((cand, marker))
        else:
            groups.append({"from_id": cand.from_id, "to_id": cand.to_id, "parts": [(cand, marker)]})
    return groups


def words_text(words, a: int, b: int) -> str:
    """Testo delle parole da a a b (incluse), con la punteggiatura originale."""
    return " ".join(w['text'] for w in words[a:b + 1])


def marker_title(kind: str, text: str) -> str:
    """Titolo del marcatore CapCut: tipo e testo tolto, al massimo MARKER_TITLE_MAX caratteri."""
    label = KIND_LABELS.get(kind, kind)
    title = f"{label}: «{text}»"
    if len(title) <= MARKER_TITLE_MAX:
        return title
    room = max(MARKER_TITLE_MAX - len(label) - len(": «…»"), 0)
    return f"{label}: «{text[:room].rstrip()}…»"


@dataclass
class CleanupCut:
    """Taglio di pulizia applicato: parole, tempi sorgente e posizione nel video finale."""
    from_id: int
    to_id: int
    kind: str
    sure: bool
    source: str
    reason: str
    text: str
    start: float
    end: float
    timeline_time: Optional[float] = None


@dataclass
class CleanupResult:
    """Esito della pulizia take di un video."""
    mode: str
    cuts: List[CleanupCut] = field(default_factory=list)
    kept: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def time_cuts(self) -> List[Tuple[float, float]]:
        """Intervalli (start, end) da passare a process_and_export come ai_cuts."""
        return [(c.start, c.end) for c in self.cuts]

    def markers(self) -> List[Dict]:
        """Marcatori CapCut dei tagli dubbi: fine del taglio (tempo sorgente) e titolo."""
        return [{"source_time": c.end, "title": marker_title(c.kind, c.text)}
                for c in self.cuts if not c.sure]


def run_cleanup(words, mode: str, cue_word: str, audio_path: Optional[str],
                video_duration: float, pad: float, client=None) -> CleanupResult:
    """
    Pulizia take completa di un video.

    :param mode: "full" (regole + Claude) o "rules" (solo regole)
    :param audio_path: WAV di analisi (16 kHz mono) per il punto più
           silenzioso; None = punto medio delle pause
    :param pad: margine (s) lasciato attorno alle parole tenute (--speech-pad)
    :param client: client Anthropic; con mode "full" e client None si passa a "rules"
    """
    result = CleanupResult(mode=mode)
    if not words:
        return result

    rule_cands = run_rules(words, cue_word)
    dubious = [c for c in rule_cands if not c.sure]
    llm = None
    if mode == "full":
        if client is None:
            result.mode = "rules"
            result.warnings.append("ANTHROPIC_API_KEY assente: pulizia con le sole regole")
        else:
            llm = review_with_claude(words, dubious, client)
            result.warnings.extend(llm.warnings)

    applied, kept = resolve_outcomes(rule_cands, dubious, llm)

    energy = None
    if audio_path:
        try:
            energy = Energy.from_wav(audio_path)
        except (OSError, ValueError, wave.Error) as e:
            result.warnings.append(f"audio di analisi non leggibile ({e}): tagli al centro delle pause")

    for group in merge_applied(applied):
        a, b = group["from_id"], group["to_id"]
        start = cut_start_time(words, a, pad, energy)
        end = cut_end_time(words, b, pad, energy, video_duration)
        if end - start < MIN_CUT:
            continue
        first = group["parts"][0][0]
        result.cuts.append(CleanupCut(
            from_id=a, to_id=b, kind=first.kind,
            sure=not any(marker for _, marker in group["parts"]),
            source="+".join(sorted({c.source for c, _ in group["parts"]})),
            reason=first.reason, text=words_text(words, a, b),
            start=round(start, 3), end=round(end, 3)))

    result.kept = [{"from_id": c.from_id, "to_id": c.to_id, "kind": c.kind, "reason": c.reason,
                    "text": words_text(words, c.from_id, c.to_id)} for c in kept]

    doubtful = sum(1 for c in result.cuts if not c.sure)
    label = "regole + Claude" if result.mode == "full" else "solo regole"
    print(f"Pulizia ({label}): {len(result.cuts)} tagli, {doubtful} da rivedere in CapCut")
    for warning in result.warnings:
        print(f"   Attenzione: {warning}")
    return result


def source_to_timeline(t: float, keep_ranges: List[Tuple[float, float]]) -> float:
    """Posizione nella timeline finale dell'istante sorgente t (un pezzo tagliato collassa sulla giunta)."""
    acc = 0.0
    for s, e in keep_ranges:
        if t <= s:
            return acc
        if t < e:
            return acc + (t - s)
        acc += e - s
    return acc
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_cleanup.py -v`
Expected: 16 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cleanup.py tests/test_cleanup.py
git commit -m "feat: orchestrazione della pulizia take e tempi dei tagli" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Report `pulizia.md` e `pulizia.json`

**Files:**
- Modify: `src/cleanup.py` (aggiunte in fondo)
- Test: `tests/test_cleanup_report.py`

**Interfaces:**
- Consumes: `CleanupCut`, `CleanupResult`, `source_to_timeline`, `KIND_LABELS`, `SOURCE_LABELS`, `intervals.measure`.
- Produces: `fmt_time(seconds) -> str` (`mm:ss,d`, `h:mm:ss,d` oltre l'ora); `context_text(words, a, b, around=CONTEXT_WORDS) -> str`; `write_report(output_folder, video_name, result, words, keep_ranges, video_duration, pause_cuts) -> (md_path, json_path)` (riempie `timeline_time` dei tagli).

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_cleanup_report.py`:

```python
import json

from cleanup import CleanupCut, CleanupResult, context_text, fmt_time, write_report
from helpers import make_words


def test_fmt_time():
    assert fmt_time(0) == "00:00,0"
    assert fmt_time(75.26) == "01:15,3"
    assert fmt_time(3725.0) == "1:02:05,0"


def test_context_text_marks_removed_words():
    words = make_words("uno due tre quattro cinque sei sette otto")
    assert context_text(words, 3, 4, around=2) == "…due tre **[quattro cinque]** sei sette…"


def test_context_text_at_start_has_no_leading_ellipsis():
    words = make_words("Buongiorno a... Ciao a tutti")
    assert context_text(words, 0, 1, around=2) == "**[Buongiorno a...]** Ciao a…"


def test_write_report_creates_markdown_and_json(tmp_path):
    words = make_words("Buongiorno a... Ciao a tutti, questo è un test")
    cut = CleanupCut(from_id=0, to_id=1, kind="false_start", sure=False, source="rule",
                     reason="frase interrotta | riformulata", text="Buongiorno a...", start=0.0, end=0.8)
    result = CleanupResult(mode="rules", cuts=[cut], kept=[], warnings=["blocco 1/1 senza Claude: prova"])
    md_path, json_path = write_report(str(tmp_path), "clip.mov", result, words,
                                      keep_ranges=[(0.8, 3.5)], video_duration=4.0, pause_cuts=[(3.5, 4.0)])
    md = open(md_path, encoding="utf-8").read()
    assert "# Pulizia take — clip.mov" in md
    assert "- Durata: 00:04,0 → 00:02,7" in md
    assert "- Tolto dalle pause: 00:00,5" in md
    assert "- Tolto dalla pulizia (oltre alle pause): 00:00,8" in md
    assert "| 00:00,0 | falsa partenza | dubbio | regola |" in md
    assert "frase interrotta \\| riformulata" in md
    assert "blocco 1/1 senza Claude: prova" in md
    data = json.load(open(json_path, encoding="utf-8"))
    assert data["mode"] == "rules"
    assert data["cuts"][0]["timeline_time"] == 0.0
    assert data["cuts"][0]["text"] == "Buongiorno a..."
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_cleanup_report.py -v`
Expected: FAIL con `ImportError: cannot import name 'context_text'`.

- [ ] **Step 3: Implementare**

Aggiungi in fondo a `src/cleanup.py`:

```python
def fmt_time(seconds: float) -> str:
    """Tempo leggibile: mm:ss,d (h:mm:ss,d oltre l'ora)."""
    tenths = int(round(max(0.0, seconds) * 10))
    hours, rest = divmod(tenths, 36000)
    minutes, rest = divmod(rest, 600)
    secs, tenth = divmod(rest, 10)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d},{tenth}"
    return f"{minutes:02d}:{secs:02d},{tenth}"


def _fmt_seconds(seconds: float) -> str:
    return f"{seconds:.1f} s".replace(".", ",")


def _cell(text: str) -> str:
    """Testo sicuro dentro una cella di tabella Markdown."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def context_text(words, a: int, b: int, around: int = CONTEXT_WORDS) -> str:
    """Parole tolte in grassetto tra parentesi quadre, con qualche parola di contesto."""
    before = words_text(words, max(0, a - around), a - 1) if a > 0 else ""
    after = words_text(words, b + 1, min(len(words) - 1, b + around))
    text = f"**[{words_text(words, a, b)}]**"
    if before:
        text = f"{'…' if a - around > 0 else ''}{before} {text}"
    if after:
        text = f"{text} {after}{'…' if b + 1 + around < len(words) else ''}"
    return text


def write_report(output_folder: str, video_name: str, result: CleanupResult, words,
                 keep_ranges: List[Tuple[float, float]], video_duration: float,
                 pause_cuts: List[Tuple[float, float]]) -> Tuple[str, str]:
    """
    Scrive pulizia.md (da leggere) e pulizia.json (per il banco di prova).

    :param keep_ranges: segmenti tenuti finali (da process_and_export)
    :param pause_cuts: tagli delle pause, per separare il tempo tolto da pause e pulizia
    :return: (percorso md, percorso json)
    """
    for cut in result.cuts:
        cut.timeline_time = round(source_to_timeline(cut.end, keep_ranges), 3)

    kept_total = sum(e - s for s, e in keep_ranges)
    removed_total = max(0.0, video_duration - kept_total)
    removed_pauses = min(measure(pause_cuts), removed_total)
    removed_cleanup = removed_total - removed_pauses
    doubtful = sum(1 for c in result.cuts if not c.sure)

    by_kind: Dict[str, Tuple[int, float]] = {}
    for c in result.cuts:
        count, seconds = by_kind.get(c.kind, (0, 0.0))
        by_kind[c.kind] = (count + 1, seconds + (c.end - c.start))

    mode = "regole + Claude" if result.mode == "full" else "solo regole"
    lines = [f"# Pulizia take — {video_name}", "", f"Modalità: {mode}", "",
             "## Riepilogo", "",
             f"- Durata: {fmt_time(video_duration)} → {fmt_time(kept_total)}",
             f"- Tolto dalle pause: {fmt_time(removed_pauses)}",
             f"- Tolto dalla pulizia (oltre alle pause): {fmt_time(removed_cleanup)}",
             f"- Tagli di pulizia: {len(result.cuts)} (dubbi, con marcatore in CapCut: {doubtful})",
             ""]
    if by_kind:
        lines += ["| Tipo | Tagli | Durata |", "|---|---|---|"]
        for kind, (count, seconds) in sorted(by_kind.items(), key=lambda kv: -kv[1][1]):
            lines.append(f"| {KIND_LABELS.get(kind, kind)} | {count} | {_fmt_seconds(seconds)} |")
        lines.append("")
    if result.warnings:
        lines += ["## Avvisi", ""] + [f"- {_cell(w)}" for w in result.warnings] + [""]
    lines += ["## Tagli", "", "| Tempo | Tipo | Esito | Origine | Testo | Motivo |", "|---|---|---|---|---|---|"]
    for c in sorted(result.cuts, key=lambda c: c.start):
        lines.append(f"| {fmt_time(c.timeline_time)} | {KIND_LABELS.get(c.kind, c.kind)} | "
                     f"{'sicuro' if c.sure else 'dubbio'} | {SOURCE_LABELS.get(c.source, c.source)} | "
                     f"{_cell(context_text(words, c.from_id, c.to_id))} | {_cell(c.reason)} |")
    if result.kept:
        lines += ["", "## Tenuti da Claude", "", "| Tipo | Testo | Motivo |", "|---|---|---|"]
        for k in result.kept:
            lines.append(f"| {KIND_LABELS.get(k['kind'], k['kind'])} | "
                         f"{_cell(context_text(words, k['from_id'], k['to_id']))} | {_cell(k['reason'])} |")

    md_path = os.path.join(output_folder, "pulizia.md")
    json_path = os.path.join(output_folder, "pulizia.json")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({"version": 1, "mode": result.mode, "cuts": [asdict(c) for c in result.cuts],
                   "kept": result.kept, "warnings": result.warnings}, f, ensure_ascii=False, indent=1)
    print(f"Report pulizia: {md_path}")
    return md_path, json_path
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_cleanup.py tests/test_cleanup_report.py -v`
Expected: 20 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cleanup.py tests/test_cleanup_report.py
git commit -m "feat: report pulizia.md e pulizia.json" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: CapCut — `build_draft`, marcatori e mai sovrascrivere

**Files:**
- Modify: `src/capcut_export.py`
- Test: `tests/test_capcut_export.py`

**Interfaces:**
- Consumes: il valore `MARKER_COLOR` del Task 0 passo 5.
- Produces: `capcut_export.MARKER_COLOR: str`; `build_draft(clips, project_name, project_dir, drafts_root) -> (draft_info, draft_meta_info, segments, fps)`; `_unique_project_dir(root, project_name) -> (name, path)`; `generate_capcut_project(clips, project_name, drafts_root=None) -> str | None` invariata nella firma; ogni clip accetta la chiave opzionale `"markers": [{"source_time": float, "title": str}, ...]`.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_capcut_export.py`:

```python
import json
import os

from capcut_export import MARKER_COLOR, _unique_project_dir, build_draft, generate_capcut_project


def _video_info(duration=10.0, fps="30/1"):
    return {"format": {"duration": str(duration)},
            "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": fps},
                        {"codec_type": "audio", "channels": 2}]}


def _clip(path, keep, markers=None):
    return {"keep_ranges": keep, "video_path": path, "video_info": _video_info(), "markers": markers or []}


def _marks(draft):
    return draft["time_marks"]["mark_items"]


def test_build_draft_without_markers_keeps_time_marks_none(tmp_path):
    draft, meta, segments, fps = build_draft([_clip("/v/a.mov", [(0.0, 1.0), (2.0, 3.0)])],
                                             "P", str(tmp_path / "P"), str(tmp_path))
    assert draft["time_marks"] is None
    assert len(segments) == 2 and fps == 30.0


def test_marker_goes_on_the_join_after_the_cut(tmp_path):
    clip = _clip("/v/a.mov", [(0.0, 1.0), (2.0, 3.0)], markers=[{"source_time": 2.0, "title": "ripetizione: «che che»"}])
    draft, *_ = build_draft([clip], "P", str(tmp_path / "P"), str(tmp_path))
    assert _marks(draft)[0]["time_range"] == {"start": 1_000_000, "duration": 0}
    assert _marks(draft)[0]["title"] == "ripetizione: «che che»"
    assert _marks(draft)[0]["color"] == MARKER_COLOR


def test_marker_after_last_segment_goes_to_timeline_end(tmp_path):
    clip = _clip("/v/a.mov", [(0.0, 1.0)], markers=[{"source_time": 5.0, "title": "x"}])
    draft, *_ = build_draft([clip], "P", str(tmp_path / "P"), str(tmp_path))
    assert _marks(draft)[0]["time_range"]["start"] == 1_000_000


def test_markers_of_second_clip_are_offset_in_combined_project(tmp_path):
    first = _clip("/v/a.mov", [(0.0, 2.0)])
    second = _clip("/v/b.mov", [(0.0, 1.0), (3.0, 4.0)], markers=[{"source_time": 3.0, "title": "y"}])
    draft, *_ = build_draft([first, second], "P", str(tmp_path / "P"), str(tmp_path))
    assert _marks(draft)[0]["time_range"]["start"] == 3_000_000


def test_malformed_marker_is_skipped(tmp_path, capsys):
    clip = _clip("/v/a.mov", [(0.0, 1.0)], markers=[{"title": "senza tempo"}])
    draft, *_ = build_draft([clip], "P", str(tmp_path / "P"), str(tmp_path))
    assert draft["time_marks"] is None
    assert "marcatore ignorato" in capsys.readouterr().out


def test_unique_project_dir_never_reuses_existing(tmp_path):
    (tmp_path / "Video").mkdir()
    assert _unique_project_dir(str(tmp_path), "Video") == ("Video-2", str(tmp_path / "Video-2"))
    (tmp_path / "Video-2").mkdir()
    assert _unique_project_dir(str(tmp_path), "Video")[0] == "Video-3"


def test_generate_does_not_overwrite_existing_project(tmp_path):
    existing = tmp_path / "Video"
    existing.mkdir()
    (existing / "draft_info.json").write_text("montaggio manuale", encoding="utf-8")
    project_dir = generate_capcut_project([_clip("/v/a.mov", [(0.0, 1.0)])], "Video", drafts_root=str(tmp_path))
    assert project_dir == str(tmp_path / "Video-2")
    assert (existing / "draft_info.json").read_text(encoding="utf-8") == "montaggio manuale"
    draft = json.load(open(os.path.join(project_dir, "draft_info.json"), encoding="utf-8"))
    assert draft["name"] == "Video-2"
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_capcut_export.py -v`
Expected: FAIL con `ImportError: cannot import name 'MARKER_COLOR'`.

- [ ] **Step 3: Implementare**

Modifiche a `src/capcut_export.py`, in ordine:

1. Nel docstring di testa, dopo la riga `Formato verificato con CapCut 9.x (macOS). I tempi sono in microsecondi.`, aggiungi:

```
I tagli dubbi della pulizia take diventano marcatori della timeline
(draft_info["time_marks"], formato letto da draft reali di CapCut 9.4).
Un progetto esistente con lo stesso nome non viene mai sovrascritto.
```

2. Dopo `MICROSECONDS = 1_000_000` aggiungi (sostituisci `#00c1cd` con il colore registrato al Task 0 passo 5; se quel passo è stato saltato lascia `#00c1cd`):

```python
# Colore dei marcatori dei tagli dubbi: diverso dal ciano di default
# (#00c1cd), che l'utente usa per le sue note. Valore della palette CapCut
# letto da un marcatore creato a mano.
MARKER_COLOR = "#00c1cd"
```

3. Dopo la funzione `_build_segment` aggiungi:

```python
def _unique_project_dir(root: str, project_name: str) -> Tuple[str, str]:
    """
    Nome e cartella liberi per il progetto: "nome", poi "nome-2", "nome-3"...
    Un progetto esistente (magari rifinito a mano) non va mai sovrascritto.
    """
    name = project_name
    suffix = 2
    while os.path.exists(os.path.join(root, name)):
        name = f"{project_name}-{suffix}"
        suffix += 1
    return name, os.path.join(root, name)


def _marker_target_us(clip_segments: List[Tuple[int, int, int]], source_time: float, fps: float) -> int:
    """
    Posizione in timeline (µs) di un marcatore: l'inizio del primo segmento
    della clip che parte dopo il taglio (la giunta). Se il taglio è dopo
    l'ultimo segmento, la fine della clip in timeline.

    :param clip_segments: [(source_start_us, target_start_us, duration_us), ...]
    """
    half_frame_us = (MICROSECONDS / fps) / 2 if fps > 0 else 0
    source_us = _sec_to_us(source_time)
    for source_start_us, target_start_us, _ in clip_segments:
        if source_start_us >= source_us - half_frame_us:
            return target_start_us
    _, last_target_us, last_duration_us = clip_segments[-1]
    return last_target_us + last_duration_us


def _build_time_marks(mark_items: List[Dict]) -> Optional[Dict]:
    """Marcatori della timeline (draft_info["time_marks"]); None se non ce ne sono."""
    if not mark_items:
        return None
    return {"id": _uuid(), "mark_items": sorted(mark_items, key=lambda m: m["time_range"]["start"])}
```

4. Trasforma l'attuale `generate_capcut_project` in `build_draft`:
   - sostituisci la riga della firma e il docstring (da `def generate_capcut_project(clips: List[Dict],` fino alla chiusura del docstring, `:return: Percorso della cartella progetto, o None se errore` + `"""`) con:

```python
def build_draft(clips: List[Dict], project_name: str, project_dir: str,
                drafts_root: str) -> Tuple[Dict, Dict, List[Dict], float]:
    """
    Costruzione pura del draft CapCut (nessuna scrittura su disco).

    :param clips: come generate_capcut_project; ogni clip può avere
           "markers": [{"source_time": secondi, "title": str}, ...]
    :param project_name: Nome definitivo del progetto
    :param project_dir: Cartella del progetto (scritta nel draft)
    :param drafts_root: Cartella dei draft CapCut
    :return: (draft_info, draft_meta_info, segmenti, fps)
    """
```

   - elimina il blocco da `clips = [c for c in clips if c.get("keep_ranges")]` fino a `os.makedirs(project_dir, exist_ok=True)` incluso;
   - sostituisci il blocco da `segments = []` fino a `target_start_us += clip_duration_us` (il ciclo sulle clip) con:

```python
    segments = []
    target_start_us = 0
    mark_items = []

    for clip in clips:
        material_uuid = _uuid()
        video_material = _build_video_material(
            clip["video_path"], clip["video_info"], material_uuid, fps
        )
        materials["videos"].append(video_material)

        clip_segments = []  # (source_start_us, target_start_us, duration_us) di questa clip
        for start, end in clip["keep_ranges"]:
            # Snap al frame: il taglio viene allineato alla griglia del
            # progetto, così l'inizio clip non può scivolare a 0.
            source_start_us = _seconds_to_frame_us(start, fps)
            source_end_us = _seconds_to_frame_us(end, fps)
            if source_end_us <= source_start_us:
                source_end_us = source_start_us + min_duration_us

            clip_duration_us = _duration_us(source_start_us, source_end_us, fps)
            segments.append(_build_segment(
                material_uuid, source_start_us, source_end_us,
                target_start_us, extra_refs, clip_duration_us
            ))
            clip_segments.append((source_start_us, target_start_us, clip_duration_us))
            target_start_us += clip_duration_us

        # Marcatori dei tagli dubbi: sulla giunta della timeline finale
        for marker in clip.get("markers") or []:
            try:
                start_us = _marker_target_us(clip_segments, float(marker["source_time"]), fps)
                title = str(marker["title"])
            except (KeyError, TypeError, ValueError, IndexError) as e:
                print(f"Attenzione: marcatore ignorato ({e!r})")
                continue
            mark_items.append({
                "id": _uuid(),
                "time_range": {"start": start_us, "duration": 0},
                "color": MARKER_COLOR,
                "title": title,
            })
```

   - nel dict `draft_info` sostituisci `"time_marks": None,` con `"time_marks": _build_time_marks(mark_items),`;
   - nel dict `draft_meta_info` sostituisci `"draft_root_path": root,` con `"draft_root_path": drafts_root,`;
   - elimina tutto da `try:` (scrittura di `draft_info.json`) fino alla fine della funzione e metti al suo posto:

```python
    return draft_info, draft_meta_info, segments, fps
```

5. Subito dopo `build_draft` aggiungi la nuova `generate_capcut_project`:

```python
def generate_capcut_project(clips: List[Dict],
                            project_name: str,
                            drafts_root: Optional[str] = None) -> Optional[str]:
    """
    Genera un progetto CapCut con la timeline dei video tagliati.

    Supporta clip multiple: ogni clip diventa un materiale video e i suoi
    segmenti vengono posti in sequenza sulla stessa traccia della timeline.
    Un progetto esistente con lo stesso nome non viene mai sovrascritto:
    si crea "nome-2", "nome-3"...

    :param clips: Lista di clip, ognuna un dict con:
                  - keep_ranges: segmenti mantenuti [(start, end), ...] in secondi
                  - video_path: percorso del video sorgente (linkato, non copiato)
                  - video_info: informazioni video da ffprobe
                  - markers (opzionale): [{"source_time": secondi, "title": str}, ...]
    :param project_name: Nome del progetto CapCut
    :param drafts_root: Cartella draft CapCut (default: percorso standard macOS)
    :return: Percorso della cartella progetto, o None se errore
    """
    clips = [c for c in clips if c.get("keep_ranges")]
    if not clips:
        print("Nessun segmento da esportare nel progetto CapCut.")
        return None

    root = drafts_root or CAPCUT_DRAFTS_ROOT
    if not os.path.isdir(root):
        print(f"Cartella draft CapCut non trovata: {root}")
        print("   CapCut non installato o mai avviato. Progetto non generato.")
        return None

    requested_name = project_name
    project_name, project_dir = _unique_project_dir(root, project_name)
    if project_name != requested_name:
        print(f"Esiste già un progetto CapCut \"{requested_name}\": creo \"{project_name}\"")

    draft_info, draft_meta_info, segments, fps = build_draft(clips, project_name, project_dir, root)

    try:
        os.makedirs(project_dir)
        with open(os.path.join(project_dir, "draft_info.json"), 'w', encoding='utf-8') as f:
            json.dump(draft_info, f, ensure_ascii=False)
        with open(os.path.join(project_dir, "draft_meta_info.json"), 'w', encoding='utf-8') as f:
            json.dump(draft_meta_info, f, ensure_ascii=False)
    except OSError as e:
        print(f"Errore scrittura progetto CapCut: {e}")
        return None

    # Controllo di sicurezza: ogni tempo deve essere un multiplo esatto di
    # 1/fps, altrimenti CapCut riallinea i tagli (rischio inizio clip a 0).
    # La tolleranza è mezza unità di frame: a 60fps il frame non è un numero
    # intero di microsecondi (16666.666...), quindi un residuo di
    # arrotondamento di pochi us è normale e NON è un disallineamento.
    frame_us = MICROSECONDS / fps if fps > 0 else MICROSECONDS

    def _is_aligned(value: int) -> bool:
        if fps <= 0:
            return True
        return abs(value - round(value / frame_us) * frame_us) < frame_us / 2

    misaligned = [
        (s['source_timerange']['start'], s['target_timerange']['start'])
        for s in segments
        if not _is_aligned(s['source_timerange']['start'])
        or not _is_aligned(s['source_timerange']['duration'])
        or not _is_aligned(s['target_timerange']['start'])
        or not _is_aligned(s['target_timerange']['duration'])
    ]
    if misaligned:
        print(f"Attenzione: {len(misaligned)} segmenti non allineati al frame ({fps} fps): "
              "CapCut potrebbe riallineare i tagli.")

    marks = (draft_info.get("time_marks") or {}).get("mark_items", [])
    print(f"Progetto CapCut generato: {project_name}")
    print(f"   ({len(draft_info['materials']['videos'])} clip, {len(segments)} segmenti, "
          f"{draft_info['duration'] / MICROSECONDS:.1f}s di timeline)")
    if marks:
        print(f"   {len(marks)} marcatori da rivedere (tagli dubbi)")
    print("   Apri CapCut: il progetto appare nella home.")
    return project_dir
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest tests/test_capcut_export.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capcut_export.py tests/test_capcut_export.py
git commit -m "feat: marcatori CapCut e nessuna sovrascrittura dei progetti" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Integrazione nella pipeline, flag e documentazione

**Files:**
- Modify: `src/video_processing.py`, `main.py`, `README.md`, `.env.example`
- Test: `tests/test_video_processing.py`, `tests/test_main_args.py`

**Interfaces:**
- Consumes: `transcription.load_words_json`, `save_words_json`; `cleanup.run_cleanup`, `write_report`; `cleanup_llm.make_client`; `CleanupResult.time_cuts()`, `.markers()`.
- Produces: `video_processing.MIN_SEGMENT_DURATION = 0.1`; `compute_keep_ranges(silence_cuts, ai_cuts, video_duration) -> list[tuple[float, float]]`; `clear_old_chunks(chunks_dir) -> None`; `process_and_export(..., markers=None)`; `main.build_parser() -> argparse.ArgumentParser` con `--cleanup`, `--cue-word`, `--retranscribe`, `--no-metadata`; `process_single_video` restituisce anche `"markers"`.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_video_processing.py`:

```python
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
```

`tests/test_main_args.py`:

```python
from main import build_parser


def test_new_cleanup_flags_defaults():
    args = build_parser().parse_args(["video.mov"])
    assert args.cleanup == "full"
    assert args.cue_word == "rifaccio"
    assert args.retranscribe is False
    assert args.no_metadata is False


def test_cleanup_flags_parse():
    args = build_parser().parse_args(["video.mov", "--cleanup", "rules", "--cue-word", "",
                                      "--retranscribe", "--no-metadata"])
    assert (args.cleanup, args.cue_word, args.retranscribe, args.no_metadata) == ("rules", "", True, True)
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_video_processing.py tests/test_main_args.py -v`
Expected: FAIL con `ImportError: cannot import name 'MIN_SEGMENT_DURATION'` e `ImportError: cannot import name 'build_parser'`.

- [ ] **Step 3: Implementare `src/video_processing.py`**

1. Agli import aggiungi `import glob` (dopo `import os`).
2. Dopo gli import aggiungi:

```python
# Durata minima di un segmento tenuto (evita segmenti troppo corti che causano errori in FFmpeg)
MIN_SEGMENT_DURATION = 0.1


def compute_keep_ranges(silence_cuts: List[Tuple[float, float]],
                        ai_cuts: List[Tuple[float, float]],
                        video_duration: float) -> List[Tuple[float, float]]:
    """
    Segmenti da tenere: complemento dell'unione dei tagli (pause + pulizia).

    :return: [(start, end), ...] ordinati; i segmenti più corti di
             MIN_SEGMENT_DURATION vengono scartati
    """
    all_cuts = sorted(list(silence_cuts) + list(ai_cuts), key=lambda x: x[0])

    merged_cuts = []
    if all_cuts:
        curr_start, curr_end = all_cuts[0]
        for next_start, next_end in all_cuts[1:]:
            if next_start < curr_end:
                curr_end = max(curr_end, next_end)
            else:
                merged_cuts.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged_cuts.append((curr_start, curr_end))

    keep_ranges = []
    current_pos = 0.0
    for cs, ce in merged_cuts:
        duration = cs - current_pos
        if cs > current_pos and duration >= MIN_SEGMENT_DURATION:
            keep_ranges.append((current_pos, cs))
        current_pos = max(current_pos, ce)

    final_duration = video_duration - current_pos
    if final_duration >= MIN_SEGMENT_DURATION:
        keep_ranges.append((current_pos, video_duration))
    return keep_ranges


def clear_old_chunks(chunks_dir: str) -> None:
    """
    Elimina i chunk di un'elaborazione precedente (c_*.mp4): se ora i
    segmenti sono meno, resterebbero file vecchi mescolati ai nuovi.
    """
    for old_chunk in glob.glob(os.path.join(chunks_dir, "c_*.mp4")):
        os.remove(old_chunk)
```

3. In `cut_video_segments`, subito dopo `os.makedirs(chunks_dir, exist_ok=True)`, aggiungi:

```python
    clear_old_chunks(chunks_dir)
```

4. In `process_and_export`:
   - alla firma aggiungi, dopo `export_capcut: bool = True`, il parametro `markers: Optional[List[Dict]] = None`;
   - nel docstring, dopo la riga di `export_capcut`, aggiungi `:param markers: Marcatori CapCut dei tagli dubbi [{"source_time", "title"}, ...] (opzionale)`;
   - sostituisci tutto il blocco dei passi 1-3 (da `# 1. Unisci tutti i tagli e ordinali` fino a `keep_ranges.append((current_pos, video_duration))` incluso) con:

```python
    # 1-3. Segmenti da mantenere (complemento dell'unione di pause e pulizia)
    keep_ranges = compute_keep_ranges(silence_cuts, ai_cuts, video_duration)
```

   - nella chiamata `generate_capcut_project(...)` aggiungi al dict della clip la chiave `"markers": markers or []`.

- [ ] **Step 4: Implementare `main.py`**

1. Sostituisci l'import `from transcription import transcribe_audio` con:

```python
from transcription import transcribe_audio, load_words_json, save_words_json
from cleanup import run_cleanup, write_report
from cleanup_llm import make_client
```

2. In `process_single_video`:
   - dopo `output_folder = os.path.join("output", video_name)` aggiungi `words_path = os.path.join(output_folder, "words.json")`;
   - sostituisci il blocco `FLUSSO 4` (da `if args.no_transcription:` fino a `words = transcription["words"]`) con:

```python
        # ============================================================
        # FLUSSO 4: TRASCRIZIONE (con timestamp parola)
        # ============================================================
        # Riusata da words.json se il video e le opzioni sono gli stessi:
        # i rilanci non rifanno la chiamata al servizio di trascrizione.
        if args.no_transcription:
            transcription = {"text": "", "words": []}
        else:
            cached = None if args.retranscribe else load_words_json(
                words_path, video_path, video_duration, args.transcriber, args.language)
            if cached:
                log_phase("Trascrizione (riusata da words.json)")
                print(f"{len(cached['words'])} parole, nessuna nuova trascrizione")
                transcription = cached
            else:
                log_phase(f"Trascrizione ({args.transcriber})")
                transcription = transcribe_audio(
                    audio_path,
                    transcriber=args.transcriber,
                    whisper_model=args.whisper_model,
                    deepgram_model=args.deepgram_model,
                    language=args.language
                )
                if transcription["words"]:
                    save_words_json(words_path, transcription, video_path, video_duration, args.language)
        transcript_text = transcription["text"]
        words = transcription["words"]
```

   - subito prima di `# Determina nome base per i file` aggiungi:

```python
        # ============================================================
        # PULIZIA TAKE (false partenze, ripetizioni, take rifatti)
        # ============================================================
        cleanup_mode = 'off' if args.no_transcription else args.cleanup
        cleanup_result = None
        if cleanup_mode != 'off':
            if words:
                log_phase("Pulizia take")
                if transcription.get("transcriber") == "whisper":
                    print("Attenzione: trascrizione Whisper, le frasi interrotte («...») "
                          "saranno riconosciute raramente")
                client = make_client() if cleanup_mode == 'full' else None
                cleanup_result = run_cleanup(
                    words, mode=cleanup_mode, cue_word=args.cue_word,
                    audio_path=audio_path, video_duration=video_duration,
                    pad=args.speech_pad, client=client
                )
            else:
                print("Pulizia take saltata: nessuna parola trascritta")
        ai_cuts = cleanup_result.time_cuts() if cleanup_result else []
        markers = cleanup_result.markers() if cleanup_result else []
```

   - nella chiamata `process_and_export(...)` sostituisci `ai_cuts=[],  # Nessun taglio AI dal CLI per ora` con `ai_cuts=ai_cuts,` e aggiungi come ultimo argomento `markers=markers`;
   - subito dopo `transcript_path = export_result["transcript_path"]` aggiungi:

```python
        if cleanup_result:
            write_report(output_folder, Path(video_path).name, cleanup_result, words,
                         export_result["keep_ranges"], video_duration, merged_silence)
```

   - sostituisci `if transcript_path and not args.no_transcription:` con `if transcript_path and not args.no_transcription and not args.no_metadata:`;
   - nel `return` finale aggiungi la chiave `"markers": markers` e nel docstring cambia `:return:` in `:return: Dict con keep_ranges, video_path finale, video_info e markers (per progetto CapCut combinato)`.

3. Estrai il parser: crea sopra `main()` la funzione `build_parser() -> argparse.ArgumentParser` e spostaci dentro, senza modificarli, tutto il blocco da `parser = argparse.ArgumentParser(` fino all'ultimo `parser.add_argument('--capcut-name', ...)`; poi aggiungi in fondo:

```python
    parser.add_argument('--cleanup', type=str, default='full', choices=['full', 'rules', 'off'],
                       help="Pulizia take: 'full' regole + Claude (richiede ANTHROPIC_API_KEY), "
                            "'rules' solo regole (gratis), 'off' solo pause (default: full)")
    parser.add_argument('--cue-word', type=str, default='rifaccio',
                       help="Parola-segnale detta da sola tra due pause per scartare il take appena "
                            "sbagliato (default: rifaccio; stringa vuota per disattivarla)")
    parser.add_argument('--retranscribe', action='store_true',
                       help='Ignora words.json e rifà la trascrizione')
    parser.add_argument('--no-metadata', action='store_true',
                       help='Salta titolo, descrizione e miniatura AI (utile per i rilanci di prova)')
    return parser
```

   e in `main()` al posto del blocco spostato scrivi `parser = build_parser()` (la riga `args = parser.parse_args()` resta).

4. Nel riepilogo iniziale di `main()`, subito dopo il blocco `if args.cut_mode != 'silence': ...`, aggiungi:

```python
    if not args.no_transcription:
        cue = f" | parola-segnale: «{args.cue_word}»" if args.cue_word and args.cleanup != 'off' else ""
        print(f"Pulizia take: {args.cleanup}{cue}")
        if args.no_metadata:
            print("Metadati AI: DISABLED")
```

- [ ] **Step 5: Aggiornare la documentazione**

In `.env.example` sostituisci `# Anthropic API Key (metadati testuali con Claude Opus 5 - opzionale)` con `# Anthropic API Key (metadati testuali e pulizia take con Claude Opus 5 - opzionale)`.

In `README.md`:
- nel blocco di "### Available Options", dopo la riga `--capcut-name MyProject   # Name of the combined CapCut project`, aggiungi:

```
  --cleanup full \          # Take cleanup: full (rules + Claude), rules, off
  --cue-word rifaccio \     # Cue word that discards the take just flubbed ("" disables it)
  --retranscribe \          # Ignore the saved words.json and transcribe again
  --no-metadata             # Skip AI title, description and thumbnail
```

- dopo la sezione "### Cut methods" aggiungi:

```markdown
### Take cleanup

On top of pauses, AutoVideoMaker removes the typical mistakes of an unscripted recording:

- **False starts**: a sentence interrupted and restarted right away ("Buongiorno a... Ciao a tutti")
- **Stutters**: words repeated by mistake ("delle delle", "che che")
- **Repeated takes**: the same sentence said again; the last complete version is kept
- **Takes marked with the cue word**: say **"rifaccio"** on its own, between two pauses, then repeat the sentence; the flubbed take and the cue word are removed

Content is never judged: anything you say only once stays in the video.

Deterministic rules find the candidates; Claude (`claude-opus-5`) reviews the uncertain ones and finds rephrased self-corrections. Claude only points at word numbers: cut times come from the word timestamps, at the quietest point of each pause.

Uncertain cuts are applied **and marked**: the CapCut project gets a timeline marker (not cyan, which is left for your own notes) on each of them, titled with the removed text. To undo one, drag the edge of the clip at the marker. Every cut is listed with its context in `pulizia.md` and `pulizia.json`.

| Option | Description |
|---|---|
| `--cleanup full` | Rules + Claude (default, needs `ANTHROPIC_API_KEY`, about $0.30 for a 20-minute video) |
| `--cleanup rules` | Rules only, free |
| `--cleanup off` | Pauses only, as before |
| `--cue-word WORD` | Cue word (default `rifaccio`; `--cue-word ""` disables it) |
| `--retranscribe` | Ignore the saved `words.json` and transcribe again |
| `--no-metadata` | Skip AI title, description and thumbnail (useful for test runs) |

The transcription is saved in `output/<video>/words.json` and reused when you process the same video again, with no new Deepgram call. CapCut projects are never overwritten: a second run creates `<name>-2`.
```

- nella sezione "## Output", dopo la riga di `transcript.txt`, aggiungi:

```markdown
- `words.json` - Word-level transcription with timestamps (reused on the next run)
- `pulizia.md` / `pulizia.json` - Take cleanup report: every cut with type, context and reason
```

- subito prima di "## Troubleshooting" aggiungi:

```markdown
## Testing

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

Manual check in CapCut (repeat after every CapCut major update: the draft format is reverse-engineered, tested with CapCut 9.4 on macOS):

1. Close CapCut, run `./run.sh video.mov`, open CapCut: the project shows up in the home with today's date.
2. Open it: no "damaged project" warning and no missing media.
3. Timeline markers sit on the joins of the uncertain cuts, with the removed text as title and a non-cyan color.
4. Drag the edge of the clip at a marker: the removed piece comes back.
5. Edit something, save and reopen: CapCut keeps the project.
```

- [ ] **Step 6: Verificare che tutti i test passino**

Run: `venv/bin/python -m pytest -v`
Expected: 93 PASS.

Run: `venv/bin/python main.py --help | grep -E "cleanup|cue-word|retranscribe|no-metadata"`
Expected: le quattro opzioni nuove con il loro aiuto.

- [ ] **Step 7: Commit**

```bash
git add src/video_processing.py main.py README.md .env.example tests/test_video_processing.py tests/test_main_args.py
git commit -m "feat: pulizia take nella pipeline, words.json e nuovi flag" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Banco di prova — `tools/evaluate_cleanup.py`

**Files:**
- Create: `tools/__init__.py` (vuoto), `tools/evaluate_cleanup.py`
- Test: `tests/test_evaluate_cleanup.py`

**Interfaces:**
- Consumes: `intervals.*`, `silence_analysis.build_speech_segments_from_words`, `invert_segments`, `video_processing.compute_keep_ranges`, `cleanup.run_cleanup`, `cleanup_llm.make_client`, `audio_extraction.extract_audio`.
- Produces: `manual_keep_ranges(draft_info, video_name) -> list`; `edl_keep_ranges(edl_path, fps) -> list`; `evaluate(manual_keep, auto_keep, new_keep, duration) -> dict` (chiavi `extra_seconds`, `covered_seconds`, `coverage`, `wrong_seconds`, `wrong`, `missed`, `buckets`); comando `python tools/evaluate_cleanup.py <cartella> [--mode rules|full]`.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_evaluate_cleanup.py`:

```python
from tools.evaluate_cleanup import edl_keep_ranges, evaluate, manual_keep_ranges


def test_manual_keep_ranges_reads_video_segments_of_the_right_file():
    draft = {"materials": {"videos": [{"id": "A", "path": "/x/clip.mov"}, {"id": "B", "path": "/x/altro.mov"}]},
             "tracks": [{"type": "video", "segments": [
                 {"material_id": "A", "source_timerange": {"start": 1_000_000, "duration": 2_000_000}},
                 {"material_id": "B", "source_timerange": {"start": 0, "duration": 5_000_000}}]},
                        {"type": "audio", "segments": []}]}
    assert manual_keep_ranges(draft, "clip.mov") == [(1.0, 3.0)]


def test_edl_keep_ranges_parses_source_timecodes(tmp_path):
    edl = tmp_path / "auto.edl"
    edl.write_text("TITLE: Video Processed\nFCM: NON-DROP FRAME\n\n"
                   "001  AX       AA/V  C        00:00:08:30 00:00:09:00 00:00:00:00 00:00:00:30\n"
                   "* FROM CLIP NAME: clip.mov\n", encoding="utf-8")
    assert edl_keep_ranges(str(edl), 60.0) == [(8.5, 9.0)]


def test_evaluate_coverage_and_extra_cuts():
    m = evaluate(manual_keep=[(0.0, 2.0), (4.0, 10.0)],   # a mano: tolti 2–4
                 auto_keep=[(0.0, 10.0)],                 # la versione automatica non tagliava niente
                 new_keep=[(0.0, 3.0), (4.0, 9.0)],       # nuova pipeline: tolti 3–4 e 9–10
                 duration=10.0)
    assert m["extra_seconds"] == 2.0
    assert m["covered_seconds"] == 1.0
    assert m["coverage"] == 0.5
    assert m["wrong_seconds"] == 1.0
    assert [b["label"] for b in m["buckets"]] == ["< 0,3 s", "0,3–1 s", "> 1 s"]
    assert m["buckets"][2]["seconds"] == 2.0
```

- [ ] **Step 2: Verificare che falliscano**

Run: `venv/bin/python -m pytest tests/test_evaluate_cleanup.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools'`.

- [ ] **Step 3: Implementare**

Crea `tools/__init__.py` vuoto e `tools/evaluate_cleanup.py`:

```python
#!/usr/bin/env python3
"""
Banco di prova della pulizia take.

Confronta i tagli della pipeline con un montaggio rifinito a mano in CapCut
(copia del draft in <cartella>/banco-prova/capcut-manuale/) e con i tagli
automatici originali (<cartella>/banco-prova/auto-originale.edl).

Uso:
  python tools/evaluate_cleanup.py "output/2026-09-16 09-10-23" [--mode rules|full]
"""

import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from intervals import complement, intersect, measure, subtract, union  # noqa: E402
from silence_analysis import build_speech_segments_from_words, invert_segments  # noqa: E402
from video_processing import compute_keep_ranges  # noqa: E402
from cleanup import run_cleanup  # noqa: E402
from cleanup_llm import make_client  # noqa: E402

BUCKETS = [(0.0, 0.3, "< 0,3 s"), (0.3, 1.0, "0,3–1 s"), (1.0, float("inf"), "> 1 s")]


def manual_keep_ranges(draft_info: dict, video_name: str) -> list:
    """Parti del video tenute nel draft CapCut (segmenti video del file video_name)."""
    materials = {m["id"]: m for m in draft_info["materials"]["videos"]}
    ranges = []
    for track in draft_info["tracks"]:
        if track.get("type") != "video":
            continue
        for seg in track["segments"]:
            material = materials.get(seg.get("material_id"))
            if not material or os.path.basename(material.get("path", "")) != video_name:
                continue
            source = seg["source_timerange"]
            start = source["start"] / 1_000_000
            ranges.append((start, start + source["duration"] / 1_000_000))
    return union(ranges)


def _timecode(tc: str, fps: float) -> float:
    hours, minutes, seconds, frames = (int(x) for x in tc.split(":"))
    return hours * 3600 + minutes * 60 + seconds + frames / fps


def edl_keep_ranges(edl_path: str, fps: float) -> list:
    """Parti tenute secondo un EDL CMX 3600 (timecode sorgente di ogni evento)."""
    ranges = []
    with open(edl_path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 8 and parts[0].isdigit():
                ranges.append((_timecode(parts[4], fps), _timecode(parts[5], fps)))
    return union(ranges)


def evaluate(manual_keep: list, auto_keep: list, new_keep: list, duration: float) -> dict:
    """
    M = tolto a mano, B = tolto dalla versione automatica originale,
    E = M \\ B (i tagli fatti a mano in più), A = tolto dalla nuova pipeline.
    """
    manual_removed = complement(manual_keep, duration)
    auto_removed = complement(auto_keep, duration)
    new_removed = complement(new_keep, duration)
    extra = subtract(manual_removed, auto_removed)
    covered = intersect(new_removed, extra)
    wrong = subtract(new_removed, manual_removed)
    buckets = []
    for lo, hi, label in BUCKETS:
        items = [(s, e) for s, e in extra if lo <= e - s < hi]
        buckets.append({"label": label, "count": len(items), "seconds": measure(items),
                        "covered": measure(intersect(new_removed, items))})
    extra_seconds = measure(extra)
    return {
        "extra_seconds": extra_seconds,
        "covered_seconds": measure(covered),
        "coverage": measure(covered) / extra_seconds if extra_seconds else 0.0,
        "wrong_seconds": measure(wrong),
        "wrong": wrong,
        "missed": subtract(extra, new_removed),
        "buckets": buckets,
    }


def interval_text(words: list, start: float, end: float) -> str:
    """Parole che cadono (anche in parte) nell'intervallo."""
    inside = [w["text"] for w in words if w["start"] < end and w["end"] > start]
    return " ".join(inside) if inside else "(pausa)"


def write_results(bench: str, mode: str, metrics: dict, words: list, result) -> str:
    """Scrive banco-prova/risultati-<data-ora>.md con metriche, tagli in più e tagli mancati."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    path = os.path.join(bench, f"risultati-{stamp}.md")
    doubtful = sum(1 for c in result.cuts if not c.sure)
    lines = [f"# Banco di prova — {stamp}", "", f"Modalità: {mode}", "",
             f"- Tagli manuali oltre ai tagli automatici originali: {metrics['extra_seconds']:.1f} s",
             f"- Coperti dalla nuova pipeline: {metrics['covered_seconds']:.1f} s ({metrics['coverage']:.0%})",
             f"- Tagli in più (tolti dalla pipeline, tenuti a mano): {metrics['wrong_seconds']:.1f} s",
             f"- Tagli di pulizia: {len(result.cuts)} ({doubtful} dubbi)",
             "", "| Durata dei tagli manuali | Numero | Secondi | Coperti |", "|---|---|---|---|"]
    for b in metrics["buckets"]:
        lines.append(f"| {b['label']} | {b['count']} | {b['seconds']:.1f} | {b['covered']:.1f} |")
    lines += ["", "## Tagli in più (da controllare)", ""]
    for s, e in sorted(metrics["wrong"], key=lambda iv: iv[0] - iv[1])[:30]:
        lines.append(f"- {s:.2f}–{e:.2f} s ({e - s:.2f} s): {interval_text(words, s, e)}")
    lines += ["", "## Tagli manuali mancati (i più lunghi)", ""]
    for s, e in sorted(metrics["missed"], key=lambda iv: iv[0] - iv[1])[:30]:
        lines.append(f"- {s:.2f}–{e:.2f} s ({e - s:.2f} s): {interval_text(words, s, e)}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(description="Banco di prova della pulizia take")
    parser.add_argument("folder", help="Cartella di output del video (con words.json e banco-prova/)")
    parser.add_argument("--mode", choices=["rules", "full"], default="rules",
                        help="rules = solo regole (gratis), full = regole + Claude")
    parser.add_argument("--cue-word", default="rifaccio")
    parser.add_argument("--word-gap", type=float, default=0.2)
    parser.add_argument("--speech-pad", type=float, default=0.05)
    args = parser.parse_args()

    bench = os.path.join(args.folder, "banco-prova")
    with open(os.path.join(args.folder, "words.json"), encoding="utf-8") as f:
        data = json.load(f)
    words = data["words"]
    duration = float(data["video"]["duration"])
    video_name = data["video"]["name"]
    with open(os.path.join(bench, "capcut-manuale", "draft_info.json"), encoding="utf-8") as f:
        draft = json.load(f)
    fps = float(draft["fps"])
    manual_keep = manual_keep_ranges(draft, video_name)
    auto_keep = edl_keep_ranges(os.path.join(bench, "auto-originale.edl"), fps)

    # Audio di analisi estratto una volta sola (separazione voce inclusa)
    audio_path = os.path.join(bench, "audio_analisi.wav")
    if not os.path.exists(audio_path):
        from audio_extraction import extract_audio
        vocals = extract_audio(os.path.join(args.folder, video_name), audio_path,
                               noise_reduction=True, separate_vocals=True)
        if vocals and os.path.exists(vocals):
            os.remove(vocals)  # serve solo l'audio di analisi a 16 kHz

    speech = build_speech_segments_from_words(words, max_gap=args.word_gap, pad=args.speech_pad,
                                              video_duration=duration)
    pause_cuts = invert_segments(speech, duration)
    client = make_client() if args.mode == "full" else None
    result = run_cleanup(words, mode=args.mode, cue_word=args.cue_word, audio_path=audio_path,
                         video_duration=duration, pad=args.speech_pad, client=client)
    new_keep = compute_keep_ranges(pause_cuts, result.time_cuts(), duration)
    metrics = evaluate(manual_keep, auto_keep, new_keep, duration)

    print(f"Tagli manuali in più: {metrics['extra_seconds']:.1f} s")
    print(f"Coperti: {metrics['covered_seconds']:.1f} s ({metrics['coverage']:.0%})")
    print(f"Tagli in più: {metrics['wrong_seconds']:.1f} s")
    print(f"Risultati: {write_results(bench, args.mode, metrics, words, result)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verificare che passino**

Run: `venv/bin/python -m pytest -v`
Expected: 96 PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/__init__.py tools/evaluate_cleanup.py tests/test_evaluate_cleanup.py
git commit -m "feat: banco di prova della pulizia take" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Verifica sul video del 16/09 e prima misura

**Files:** nessuna modifica al codice (salvo correzioni emerse, ciascuna con il suo test e commit).

**Interfaces:**
- Consumes: tutta la pipeline; `tools/evaluate_cleanup.py`; il banco di prova del Task 0.

- [ ] **Step 1: Suite completa**

Run: `venv/bin/python -m pytest -q`
Expected: tutti PASS.

- [ ] **Step 2: Rilancio della pipeline sul video del 16/09**

Costi da confermare con l'utente prima di lanciare: una trascrizione Deepgram (pochi centesimi) e un giro di Claude (~0,30 $). Con `--no-metadata` non si rigenerano titolo e miniatura.

```bash
./run.sh "output/2026-09-16 09-10-23/2026-09-16 09-10-23.mov" --no-metadata
```

Expected in console: fase `[Trascrizione (deepgram)]`, fase `[Pulizia take]` con `Pulizia (regole + Claude): N tagli, M da rivedere in CapCut`, `Esiste già un progetto CapCut "2026-09-16 09-10-23": creo "2026-09-16 09-10-23-2"`, `Report pulizia: output/2026-09-16 09-10-23/pulizia.md`. Nella cartella compare `words.json`.

- [ ] **Step 3: Il montaggio manuale è intatto**

```bash
cmp "$HOME/Movies/CapCut/User Data/Projects/com.lveditor.draft/2026-09-16 09-10-23/draft_info.json" \
    "output/2026-09-16 09-10-23/banco-prova/capcut-manuale/draft_info.json" && echo "intatto"
```

Expected: `intatto`.

- [ ] **Step 4: Verifica manuale in CapCut (con l'utente)**

Chiedi all'utente di seguire la checklist "Manual check in CapCut" del README sul progetto `2026-09-16 09-10-23-2`: apertura senza avvisi, marcatori sulle giunte con titolo e colore giusti, ripristino di un taglio trascinando il bordo della clip, salvataggio e riapertura. Se un punto fallisce, confronta il draft generato con uno creato da CapCut (`diff` sulle chiavi di `time_marks`) prima di toccare il codice.

- [ ] **Step 5: Prima misura sul banco di prova**

```bash
venv/bin/python tools/evaluate_cleanup.py "output/2026-09-16 09-10-23" --mode rules
venv/bin/python tools/evaluate_cleanup.py "output/2026-09-16 09-10-23" --mode full
```

Expected: per ciascuna modalità, copertura, tagli in più e percorso di `banco-prova/risultati-<data-ora>.md`. Al primo lancio viene estratto `banco-prova/audio_analisi.wav` (qualche minuto per la separazione della voce).

- [ ] **Step 6: Resoconto all'utente**

Riporta all'utente, con i numeri reali: copertura e tagli in più per `rules` e `full`, la suddivisione per durata dei tagli manuali, i 5 tagli in più più lunghi e i 5 tagli mancati più lunghi (dal file dei risultati). Confrontali con i criteri provvisori della spec (copertura ≥ 60% dei 158,3 s; tagli in più ≤ 10 s; nessuna frase detta una sola volta danneggiata) e proponi la taratura (soglie di `cleanup_rules.py`, `--word-gap`, `--speech-pad`). La taratura stessa è un passo successivo, da concordare.
