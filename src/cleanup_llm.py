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


def owned_ranges(windows: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Parole su cui valgono i tagli nuovi di ogni blocco: la zona condivisa con
    il blocco successivo si divide a metà, così ogni parola la decide un
    blocco solo e l'altro la vede come contesto. Senza questo i due blocchi
    possono togliere ciascuno una delle due occorrenze di un inciampo.
    """
    owned = []
    for idx, (first, last) in enumerate(windows):
        lo = first if idx == 0 else owned[-1][1] + 1
        hi = (windows[idx + 1][0] + last) // 2 if idx + 1 < len(windows) else last
        owned.append((lo, hi))
    return owned


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
    unassigned = len(numbered) - sum(len(v) for v in assigned.values())

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

    owned = owned_ranges(windows)
    result = LlmResult()
    for idx in range(len(windows)):
        label = f"blocco {idx + 1}/{len(windows)}"
        if idx in errors:
            result.failed_windows += 1
            result.warnings.append(f"{label} senza Claude: {errors[idx]}")
            continue
        verdicts, cuts, warnings = outcomes[idx]
        result.verdicts.update(verdicts)
        lo, hi = owned[idx]
        result.cuts.extend(c for c in cuts if lo <= c.from_id <= hi)
        result.warnings.extend(f"{label}: {w}" for w in warnings)
    if unassigned:
        result.warnings.append(f"{unassigned} candidati dubbi a cavallo tra due blocchi: "
                               "nessun verdetto di Claude (applicati con marcatore)")
    result.cuts.sort(key=lambda c: (c.from_id, c.to_id))
    return result
