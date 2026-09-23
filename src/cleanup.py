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
from dataclasses import asdict, dataclass, field, replace
from typing import Dict, List, Optional, Tuple

import numpy as np

from cleanup_llm import LlmResult, review_with_claude
from cleanup_rules import KIND_LABELS, REPETITION_MAX_N, Candidate, normalized, run_rules
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


def canonical_repetition(cand: Candidate, norm: List[str]) -> Candidate:
    """
    Un taglio su una ripetizione deve togliere una sola occorrenza, la prima,
    come fanno le regole. Così il taglio di Claude e quello delle regole sullo
    stesso inciampo coincidono invece di togliere entrambe le occorrenze
    («Lui dice [che che] si è dimesso» deve lasciare un «che»).
    """
    a, b = cand.from_id, cand.to_id
    n = b - a + 1
    seg = norm[a:b + 1]
    if not all(seg):
        return cand
    half = n // 2
    # tolte entrambe le occorrenze («che che»): resta la seconda
    if n % 2 == 0 and half <= REPETITION_MAX_N and seg[:half] == seg[half:]:
        return replace(cand, to_id=a + half - 1)
    # tolta la seconda occorrenza: si toglie la prima, come le regole
    if n <= REPETITION_MAX_N and a - n >= 0 and norm[a - n:a] == seg:
        return replace(cand, from_id=a - n, to_id=a - 1)
    return cand


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
            # I tagli di Claude sulle ripetizioni tolgono la prima occorrenza,
            # come le regole: un inciampo non perde mai entrambe le occorrenze
            norm = normalized(words)
            llm.cuts = [canonical_repetition(c, norm) for c in llm.cuts]

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
            result.warnings.append(f"taglio troppo corto ignorato (parole {a}–{b})")
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
