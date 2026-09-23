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
