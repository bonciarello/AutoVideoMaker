#!/usr/bin/env python3
"""
Video Silence Cutter - Orchestratore Principale
Analizza un video, identifica le parti di silenzio e genera un progetto CapCut con i tagli.

Questo è il file principale che orchestra tutti i flussi di elaborazione:
1. Verifica dipendenze
2. Estrazione audio (con separazione vocale AI)
3. Analisi silenzi
4. Trascrizione Whisper
5. Elaborazione video e export
6. Generazione metadati AI

Per vedere i singoli moduli, consulta i file in src/:
- dependency_check.py
- audio_extraction.py
- silence_analysis.py
- transcription.py
- video_processing.py
- metadata_generation.py
- utils.py
"""

import os
import sys
import argparse
import tempfile
from pathlib import Path

# Aggiungi src al path per permettere import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


# Import dei moduli personalizzati da src/
from utils import log_phase, get_video_info
from dependency_check import check_dependencies
from audio_extraction import extract_audio
from silence_analysis import analyze_audio_silence, merge_silence_intervals
from transcription import generate_subtitles_whisper
from video_processing import process_and_export, move_original_video
from metadata_generation import generate_video_metadata


def main():
    parser = argparse.ArgumentParser(
        description="Taglia automaticamente i silenzi da un video"
    )
    parser.add_argument('input_video', help='Percorso del video di input')
    parser.add_argument('-t', '--threshold', type=float, default=-40,
                       help='Soglia di silenzio in dB (default: -40)')
    parser.add_argument('-d', '--duration', type=float, default=0.5,
                       help='Durata minima del silenzio in secondi (default: 0.5)')
    parser.add_argument('-m', '--merge', type=float, default=1.0,
                       help='Distanza massima per unire silenzi vicini (default: 1.0s)')
    parser.add_argument('--whisper-model', type=str, default='medium',
                       choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='Modello Whisper per la trascrizione (default: medium)')
    parser.add_argument('--no-whisper', action='store_true',
                       help='Salta la generazione della trascrizione e metadati AI con Whisper/Gemini')

    args = parser.parse_args()

    # Stampa parametri di avvio
    print("\n" + "="*100)
    print("VIDEO SILENCE CUTTER")
    print("="*100)
    print(f"Input video: {args.input_video}")
    print(f"Threshold: {args.threshold} dB")
    print(f"Duration: {args.duration}s")
    print(f"Merge: {args.merge}s")
    if not args.no_whisper:
        print(f"Whisper model: {args.whisper_model}")
    else:
        print("Whisper: DISABLED")
    print("="*100)

    # ============================================================
    # FLUSSO 1: VERIFICA DIPENDENZE
    # ============================================================
    log_phase("Verifica dipendenze")
    check_dependencies()

    # Verifica che il file video esista
    if not os.path.exists(args.input_video):
        raise FileNotFoundError(f"File video non trovato: {args.input_video}")

    # Determina il percorso di output: output/{nome_video}/
    video_name = Path(args.input_video).stem
    output_folder = os.path.join("output", video_name)

    # ============================================================
    # ANALISI VIDEO INIZIALE
    # ============================================================
    log_phase("Analisi video")
    video_info = get_video_info(args.input_video)
    video_duration = float(video_info['format']['duration'])
    video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
    fps = eval(video_stream.get('r_frame_rate', '30/1')) if video_stream else 30.0
    print(f"Durata: {video_duration:.2f}s, FPS: {fps:.2f}")
    print(f"Output: {output_folder}")

    # Crea cartella di output prima
    os.makedirs(output_folder, exist_ok=True)

    # Crea directory temporanea
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, 'audio.wav')

        # ============================================================
        # FLUSSO 2: ESTRAZIONE AUDIO
        # ============================================================
        log_phase("Estrazione audio")
        vocals_full_path = extract_audio(
            args.input_video,
            audio_path,
            noise_reduction=True,
            separate_vocals=True
        )

        # ============================================================
        # FLUSSO 3: ANALISI SILENZI
        # ============================================================
        log_phase("Analisi silenzi")
        silence_intervals = analyze_audio_silence(
            audio_path,
            args.threshold,
            args.duration
        )

        # ============================================================
        # FLUSSO 4: TRASCRIZIONE WHISPER
        # ============================================================
        if args.no_whisper:
            transcript_text = ""
        else:
            log_phase("Trascrizione Whisper")
            transcript_text = generate_subtitles_whisper(
                args.input_video,
                model_size=args.whisper_model
            )

        # ============================================================
        # UNIONE INTERVALLI SILENZI
        # ============================================================
        log_phase("Unione intervalli silenzi")
        merged_silence = merge_silence_intervals(
            silence_intervals,
            args.merge
        )
        print(f"Intervalli da rimuovere: {len(merged_silence)}")

        # Determina nome base per i file
        name_no_ext = Path(args.input_video).stem + "_tagliato"

        # ============================================================
        # FLUSSO 5: ELABORAZIONE VIDEO E EXPORT
        # ============================================================
        log_phase("Export video e file")
        transcript_path = process_and_export(
            video_path=args.input_video,
            silence_cuts=merged_silence,
            ai_cuts=[],  # Nessun taglio AI dal CLI per ora
            video_duration=video_duration,
            output_folder=output_folder,
            video_info=video_info,
            name_no_ext=name_no_ext,
            transcript_text=transcript_text,
            save_transcript=not args.no_whisper,
            vocals_audio_path=vocals_full_path
        )

        # ============================================================
        # FLUSSO 6: GENERAZIONE METADATI AI
        # ============================================================
        if transcript_path and not args.no_whisper:
            generate_video_metadata(transcript_path, output_folder)

    # ============================================================
    # SPOSTA VIDEO ORIGINALE
    # ============================================================
    move_original_video(args.input_video, output_folder)

    print("\n" + "="*100)
    print("COMPLETATO!")
    print("="*100)
    print(f"Tutti i file sono stati salvati in: {output_folder}")


if __name__ == '__main__':
    main()
