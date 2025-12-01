#!/usr/bin/env python3
"""
Flusso 3: Analisi Silenzi
Analizza l'audio e rileva gli intervalli di silenzio.
"""

import subprocess
from typing import List, Tuple, Dict


def analyze_audio_silence(audio_path: str,
                          silence_threshold_db: float = -40,
                          min_silence_duration: float = 0.5) -> List[Tuple[float, float]]:
    """
    Analizza l'audio e trova gli intervalli di silenzio usando ffmpeg.

    :param audio_path: Percorso del file audio
    :param silence_threshold_db: Soglia di silenzio in dB (default: -40)
    :param min_silence_duration: Durata minima del silenzio in secondi (default: 0.5)
    :return: Lista di intervalli di silenzio [(start, end), ...]
    """
    print(f"Rilevando silenzi (soglia: {silence_threshold_db}dB)...", end='', flush=True)

    cmd = [
        'ffmpeg', '-i', audio_path,
        '-af', f'silencedetect=noise={silence_threshold_db}dB:d={min_silence_duration}',
        '-f', 'null', '-'
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = result.stdout

    silence_intervals = []
    silence_start = None

    for line in output.split('\n'):
        if 'silencedetect' in line:
            if 'silence_start' in line:
                parts = line.split('silence_start:')
                if len(parts) > 1:
                    silence_start = float(parts[1].strip().split()[0])
            elif 'silence_end' in line and silence_start is not None:
                parts = line.split('silence_end:')
                if len(parts) > 1:
                    silence_end = float(parts[1].strip().split()[0])
                    silence_intervals.append((silence_start, silence_end))
                    silence_start = None

    print(f"  ({len(silence_intervals)} intervalli)")
    return silence_intervals


def merge_silence_intervals(silence_intervals: List[Tuple[float, float]],
                           subtitle_segments: List[Dict] = None,
                           merge_distance: float = 1.0) -> List[Tuple[float, float]]:
    """
    Unisce gli intervalli di silenzio e considera anche le pause tra sottotitoli.

    :param silence_intervals: Lista di intervalli di silenzio dall'audio
    :param subtitle_segments: Lista di segmenti sottotitoli (opzionale)
    :param merge_distance: Distanza massima per unire intervalli vicini (secondi)
    :return: Lista di intervalli uniti
    """
    all_intervals = []

    # Aggiungi intervalli di silenzio dall'audio
    all_intervals.extend(silence_intervals)

    # Aggiungi pause tra sottotitoli
    if subtitle_segments:
        for i in range(len(subtitle_segments) - 1):
            pause_start = subtitle_segments[i]['end']
            pause_end = subtitle_segments[i + 1]['start']

            # Se c'è una pausa significativa tra sottotitoli
            if pause_end - pause_start > 0.3:
                all_intervals.append((pause_start, pause_end))

    if not all_intervals:
        return []

    # Ordina gli intervalli
    all_intervals.sort(key=lambda x: x[0])

    # Unisci intervalli vicini
    merged = [all_intervals[0]]
    for current in all_intervals[1:]:
        last = merged[-1]
        if current[0] - last[1] <= merge_distance:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)

    return merged


def calculate_kept_segments(video_duration: float,
                           silence_intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Calcola i segmenti da mantenere (inverso dei silenzi).

    :param video_duration: Durata totale del video in secondi
    :param silence_intervals: Lista di intervalli di silenzio da rimuovere
    :return: Lista di segmenti da mantenere [(start, end), ...]
    """
    if not silence_intervals:
        return [(0, video_duration)]

    kept_segments = []
    current_pos = 0

    for silence_start, silence_end in silence_intervals:
        if current_pos < silence_start:
            kept_segments.append((current_pos, silence_start))
        current_pos = max(current_pos, silence_end)

    # Aggiungi l'ultimo segmento se c'è
    if current_pos < video_duration:
        kept_segments.append((current_pos, video_duration))

    return kept_segments


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python 3_silence_analysis.py <audio_path>")
        sys.exit(1)

    audio = sys.argv[1]
    intervals = analyze_audio_silence(audio)
    print(f"\nIntervalli di silenzio trovati: {len(intervals)}")
    for i, (start, end) in enumerate(intervals[:5], 1):
        print(f"  {i}. {start:.2f}s - {end:.2f}s (durata: {end-start:.2f}s)")
    if len(intervals) > 5:
        print(f"  ... e altri {len(intervals)-5} intervalli")
