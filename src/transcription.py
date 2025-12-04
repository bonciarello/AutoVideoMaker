#!/usr/bin/env python3
"""
Flusso 4: Trascrizione Whisper
Genera sottotitoli usando Whisper AI con segmentazione intelligente.
"""

from typing import List, Dict, Optional
from utils import format_timestamp_srt


def generate_subtitles_whisper(video_path: str,
                               output_srt: str = None,
                               words_per_segment: int = 3,
                               model_size: str = "medium") -> str:
    """
    Genera trascrizione usando Whisper (solo testo, senza timestamp).

    :param video_path: Percorso del video
    :param output_srt: Non usato, mantenuto per compatibilità
    :param words_per_segment: Non usato, mantenuto per compatibilità
    :param model_size: Dimensione del modello Whisper (tiny, base, small, medium, large, default: medium)
    :return: Testo completo della trascrizione
    """
    try:
        import whisper
        print(f"Generando trascrizione con Whisper {model_size}...")

        model = whisper.load_model(model_size)
        # Trascrizione semplice senza timestamp
        result = model.transcribe(video_path, language="it")

        # Estrai solo il testo completo
        full_text = result['text'].strip()

        return full_text
    except ImportError:
        print("ATTENZIONE: openai-whisper non è installato. Installalo con: pip install openai-whisper")
        return ""


def resegment_subtitles(segments: List[Dict], words_per_segment: int = 8) -> List[Dict]:
    """
    Ri-segmenta i sottotitoli raggruppando più parole insieme.

    :param segments: Lista di segmenti originali (con 3 parole)
    :param words_per_segment: Numero di parole per il nuovo segmento (default: 8)
    :return: Lista di segmenti ri-segmentati
    """
    if not segments:
        return []

    # Unisci tutti i segmenti e conta le parole
    all_words = []
    for seg in segments:
        words = seg['text'].split()
        for word in words:
            all_words.append({
                'word': word,
                'time': seg['start'] + (seg['end'] - seg['start']) * (words.index(word) / max(len(words), 1))
            })

    # Ri-segmenta in gruppi di N parole
    new_segments = []
    for i in range(0, len(all_words), words_per_segment):
        word_group = all_words[i:i + words_per_segment]
        if word_group:
            new_segments.append({
                'start': word_group[0]['time'],
                'end': word_group[-1]['time'] + 0.5,  # Aggiungi 0.5s alla fine
                'text': ' '.join([w['word'] for w in word_group])
            })

    return new_segments


def save_subtitles_json(segments: List[Dict], output_json: str, video_path: str = None) -> None:
    """Salva i sottotitoli in formato JSON con metadata."""
    import json
    from datetime import datetime

    data = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'video_path': video_path if video_path else 'unknown',
            'total_segments': len(segments),
            'duration': segments[-1]['end'] if segments else 0
        },
        'segments': segments
    }

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_subtitles_txt(segments: List[Dict], output_txt: str) -> None:
    """Salva i sottotitoli in formato TXT (solo testo trascritto)."""
    with open(output_txt, 'w', encoding='utf-8') as f:
        for segment in segments:
            f.write(f"{segment['text']}\n")


def save_subtitles_srt(segments: List[Dict], output_srt: str) -> None:
    """Salva i sottotitoli in formato SRT."""
    with open(output_srt, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp_srt(segment['start'])} --> {format_timestamp_srt(segment['end'])}\n")
            f.write(f"{segment['text']}\n\n")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python 4_transcription.py <video_path> [output_srt]")
        sys.exit(1)

    video = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None
    segments = generate_subtitles_whisper(video, output)
    print(f"\nSegmenti generati: {len(segments)}")
    if segments:
        print(f"Primo segmento: {segments[0]['text']}")
        print(f"Ultimo segmento: {segments[-1]['text']}")
