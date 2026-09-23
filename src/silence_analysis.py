#!/usr/bin/env python3
"""
Flusso 3: Analisi Silenzi
Analizza l'audio e rileva gli intervalli di silenzio.
"""

import subprocess
from typing import List, Tuple, Dict, Optional


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
                           merge_distance: float = 1.0) -> List[Tuple[float, float]]:
    """
    Unisce gli intervalli di silenzio vicini.

    :param silence_intervals: Lista di intervalli di silenzio dall'audio
    :param merge_distance: Distanza massima per unire intervalli vicini (secondi)
    :return: Lista di intervalli uniti
    """
    if not silence_intervals:
        return []

    # Ordina gli intervalli
    sorted_intervals = sorted(silence_intervals, key=lambda x: x[0])

    # Unisci intervalli vicini
    merged = [sorted_intervals[0]]
    for current in sorted_intervals[1:]:
        last = merged[-1]
        if current[0] - last[1] <= merge_distance:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)

    return merged


def build_speech_segments_from_words(words: List[Dict],
                                     max_gap: float = 0.2,
                                     pad: float = 0.05,
                                     video_duration: Optional[float] = None) -> List[Tuple[float, float]]:
    """
    Costruisce i segmenti parlati dai timestamp delle parole (da trascrizione).

    Approccio più preciso del silencedetect: i tagli avvengono esattamente
    tra una parola e l'altra, mai in mezzo al parlato. Un padding di
    sicurezza protegge l'attacco e il rilascio delle parole ai bordi.

    :param words: Lista di parole con timestamp [{"start", "end", "word"}, ...]
    :param max_gap: Pausa massima tra due parole nello stesso segmento (secondi).
           Default 0.2: le pause piu' lunghe vengono tagliate.
    :param pad: Margine di sicurezza aggiunto ai bordi di ogni segmento (secondi).
           Il silenzio che resta dopo ogni taglio vale 2*pad: con 0.05 sono
           100ms totali (prima 2*0.15 = 300ms).
    :param video_duration: Durata totale del video (per clamp dei bordi)
    :return: Lista di segmenti parlati [(start, end), ...] ordinati e non sovrapposti
    """
    if not words:
        return []

    # Il padding e' applicato a entrambi i lati: se superasse meta' del gap
    # minimo, i segmenti adiacenti si sovrapporrebbero e il margine non
    # verrebbe tagliato affatto. Tengo quindi pad < max_gap/2.
    pad = min(pad, max_gap / 2)

    sorted_words = sorted(words, key=lambda w: w['start'])

    # Raggruppa le parole in segmenti: pausa > max_gap = nuovo segmento
    segments = []
    seg_start = sorted_words[0]['start']
    seg_end = sorted_words[0]['end']

    for w in sorted_words[1:]:
        if w['start'] - seg_end <= max_gap:
            seg_end = max(seg_end, w['end'])
        else:
            segments.append((seg_start, seg_end))
            seg_start = w['start']
            seg_end = w['end']
    segments.append((seg_start, seg_end))

    # Applica padding e clamp ai bordi del video
    max_end = video_duration if video_duration is not None else float('inf')
    padded = [(max(0.0, s - pad), min(max_end, e + pad)) for s, e in segments]

    # Unisci eventuali sovrapposizioni create dal padding
    return merge_silence_intervals(padded, merge_distance=0.0)


def invert_segments(speech_segments: List[Tuple[float, float]],
                    video_duration: float) -> List[Tuple[float, float]]:
    """
    Calcola gli intervalli da tagliare come complemento dei segmenti parlati.

    :param speech_segments: Segmenti da mantenere [(start, end), ...]
    :param video_duration: Durata totale del video in secondi
    :return: Lista di intervalli da rimuovere [(start, end), ...]
    """
    cuts = []
    pos = 0.0

    for start, end in sorted(speech_segments):
        if start > pos:
            cuts.append((pos, start))
        pos = max(pos, end)

    if pos < video_duration:
        cuts.append((pos, video_duration))

    return cuts


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
