#!/usr/bin/env python3
"""
Esempio di utilizzo della funzione process_and_export
"""

from video_silence_cutter import (
    process_and_export,
    get_video_info,
    generate_subtitles_whisper
)
import os

# Esempio di utilizzo
if __name__ == "__main__":
    # Parametri del tuo video
    video_path = "path/to/your/video.mp4"
    output_folder = "output"

    # Esempio di tagli da silenzi (in secondi)
    silence_cuts = [
        (10.5, 15.2),   # Silenzio da 10.5s a 15.2s
        (30.0, 35.8),   # Silenzio da 30.0s a 35.8s
        (60.1, 62.5),   # Silenzio da 60.1s a 62.5s
    ]

    # Esempio di tagli AI (in secondi)
    ai_cuts = [
        (20.0, 22.5),   # Taglio AI da 20.0s a 22.5s
        (45.0, 48.0),   # Taglio AI da 45.0s a 48.0s
    ]

    # Ottieni informazioni sul video
    video_info = get_video_info(video_path)
    video_duration = float(video_info['format']['duration'])

    # [OPZIONALE] Genera sottotitoli con Whisper
    # Richiede: pip install openai-whisper
    subtitle_segments = None
    try:
        # Genera sottotitoli (solo in memoria, nessun file temporaneo)
        # words_per_segment: numero di parole per segmento (default: 4)
        # Usa 3-4 per sottotitoli brevi, 6-8 per sottotitoli più lunghi
        subtitle_segments = generate_subtitles_whisper(
            video_path=video_path,
            words_per_segment=4  # Segmenti di ~4 parole
        )
        print(f"✓ Sottotitoli generati: {len(subtitle_segments)} segmenti")
        print(f"  (Saranno salvati definitivamente in '{output_folder}/')\n")
    except Exception as e:
        print(f"⚠️  Sottotitoli non disponibili: {e}\n")

    # Processa ed esporta
    process_and_export(
        video_path=video_path,
        silence_cuts=silence_cuts,
        ai_cuts=ai_cuts,
        video_duration=video_duration,
        output_folder=output_folder,
        video_info=video_info,
        name_no_ext="mio_video_tagliato",
        subtitle_segments=subtitle_segments,  # Passa i sottotitoli se disponibili
        save_subtitles=True  # Salva i sottotitoli in 3 formati (SRT, JSON, TXT)
    )

    print("\n✓ Processo completato!")
    print(f"\n📁 File generati in '{output_folder}/':")
    print(f"  - EDL (Premiere Pro): mio_video_tagliato.edl")
    print(f"  - Video finale: FINAL_mio_video_tagliato.mp4")
    if subtitle_segments:
        print(f"  - Sottotitoli SRT: mio_video_tagliato.srt")
        print(f"  - Sottotitoli JSON: mio_video_tagliato_subtitles.json")
        print(f"  - Trascrizione TXT: mio_video_tagliato_transcript.txt")
