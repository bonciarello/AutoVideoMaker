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
from cleanup_rules import KIND_LABELS  # noqa: E402

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


def snap_to_frames(intervals: list, fps: float) -> list:
    """Allinea gli intervalli alla griglia dei frame, come fanno EDL e CapCut."""
    return union((round(s * fps) / fps, round(e * fps) / fps) for s, e in intervals)


def _drop_short(intervals: list, min_len: float) -> list:
    """Scarta le schegge più corte di min_len: arrotondamenti al frame, non tagli veri."""
    return [(s, e) for s, e in intervals if e - s >= min_len]


def evaluate(manual_keep: list, auto_keep: list, new_keep: list, duration: float, min_len: float = 0.0) -> dict:
    """
    M = tolto a mano, B = tolto dalla versione automatica originale,
    E = M \\ B (i tagli fatti a mano in più), A = tolto dalla nuova pipeline.

    :param min_len: schegge più corte di così (arrotondamenti al frame, non
           tagli veri) sono scartate da extra, wrong e missed.
    """
    manual_removed = complement(manual_keep, duration)
    auto_removed = complement(auto_keep, duration)
    new_removed = complement(new_keep, duration)
    extra = _drop_short(subtract(manual_removed, auto_removed), min_len)
    covered = intersect(new_removed, extra)
    wrong = _drop_short(subtract(new_removed, manual_removed), min_len)
    buckets = []
    for lo, hi, label in BUCKETS:
        items = [(s, e) for s, e in extra if lo <= e - s < hi]
        buckets.append({"label": label, "count": len(items), "seconds": measure(items),
                        "covered": measure(intersect(new_removed, items))})
    extra_seconds = measure(extra)
    return {
        "extra_seconds": extra_seconds,
        "extra": extra,
        "covered_seconds": measure(covered),
        "coverage": measure(covered) / extra_seconds if extra_seconds else 0.0,
        "wrong_seconds": measure(wrong),
        "wrong": wrong,
        "missed": _drop_short(subtract(extra, new_removed), min_len),
        "buckets": buckets,
    }


def cuts_breakdown(cleanup_cuts, pause_cuts: list, extra: list, manual_removed: list) -> list:
    """
    Tagli automatici per tipo e origine (pause comprese): quanti sono, quanti
    secondi tolgono, quanti cadono nei tagli manuali in più (E, utili) e
    quanti in parti che a mano erano state tenute (in più).
    """
    groups = {}
    for s, e in pause_cuts:
        groups.setdefault(("pause", "pause"), []).append((s, e))
    for cut in cleanup_cuts:
        groups.setdefault((cut.kind, cut.source), []).append((cut.start, cut.end))
    rows = []
    for (kind, source), items in sorted(groups.items()):
        rows.append({"kind": kind, "source": source, "count": len(items),
                     "seconds": measure(items),
                     "useful": measure(intersect(items, extra)),
                     "wrong": measure(subtract(items, manual_removed))})
    return rows


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
    if metrics.get("by_type"):
        lines += ["", "| Tipo | Origine | Tagli | Secondi | Utili (nei tagli manuali in più) | In più (tenuti a mano) |",
                  "|---|---|---|---|---|---|"]
        for r in metrics["by_type"]:
            label = "pausa" if r["kind"] == "pause" else KIND_LABELS.get(r["kind"], r["kind"])
            lines.append(f"| {label} | {r['source']} | {r['count']} | {r['seconds']:.1f} | "
                         f"{r['useful']:.1f} | {r['wrong']:.1f} |")
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
    new_keep = snap_to_frames(compute_keep_ranges(pause_cuts, result.time_cuts(), duration), fps)
    metrics = evaluate(manual_keep, auto_keep, new_keep, duration, min_len=1.5 / fps)
    metrics["by_type"] = cuts_breakdown(result.cuts, pause_cuts, metrics["extra"],
                                        complement(manual_keep, duration))

    print(f"Tagli manuali in più: {metrics['extra_seconds']:.1f} s")
    print(f"Coperti: {metrics['covered_seconds']:.1f} s ({metrics['coverage']:.0%})")
    print(f"Tagli in più: {metrics['wrong_seconds']:.1f} s")
    print(f"Risultati: {write_results(bench, args.mode, metrics, words, result)}")


if __name__ == "__main__":
    main()
