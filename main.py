#!/usr/bin/env python3
"""
AutoVideoMaker - Main Orchestrator
Analyzes videos, identifies silence portions and generates cut videos with AI metadata.

This is the main file that orchestrates all processing flows:
1. Dependency verification
2. Audio extraction (with AI vocal separation)
3. Silence analysis
4. Whisper transcription
5. Video processing and export
6. AI metadata generation

To see individual modules, check the files in src/:
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
import glob
from pathlib import Path
from typing import List

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


def expand_video_files(patterns: List[str]) -> List[str]:
    """
    Espande pattern glob e verifica che i file esistano.

    :param patterns: Lista di percorsi o pattern glob
    :return: Lista di file video esistenti
    """
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
    video_files = []

    for pattern in patterns:
        # Espandi il pattern glob
        matches = glob.glob(pattern, recursive=True)

        if not matches:
            # Se non ci sono match, prova come percorso diretto
            if os.path.exists(pattern):
                matches = [pattern]

        # Filtra solo i file video
        for match in matches:
            if os.path.isfile(match):
                ext = os.path.splitext(match)[1].lower()
                if ext in video_extensions:
                    video_files.append(os.path.abspath(match))

    return video_files


def process_single_video(video_path: str, args: argparse.Namespace, video_num: int = 0, total_videos: int = 1) -> None:
    """
    Elabora un singolo video.

    :param video_path: Percorso del video
    :param args: Argomenti da linea di comando
    :param video_num: Numero del video corrente (per display)
    :param total_videos: Totale video da elaborare
    """
    print("\n" + "="*100)
    if total_videos > 1:
        print(f"VIDEO {video_num}/{total_videos}: {os.path.basename(video_path)}")
    else:
        print(f"VIDEO: {os.path.basename(video_path)}")
    print("="*100)

    # Determina il percorso di output: output/{nome_video}/
    video_name = Path(video_path).stem
    output_folder = os.path.join("output", video_name)

    # ============================================================
    # ANALISI VIDEO INIZIALE
    # ============================================================
    log_phase("Analisi video")
    video_info = get_video_info(video_path)
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
            video_path,
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
                video_path,
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
        name_no_ext = Path(video_path).stem + "_tagliato"

        # ============================================================
        # FLUSSO 5: ELABORAZIONE VIDEO E EXPORT
        # ============================================================
        log_phase("Export video e file")
        transcript_path = process_and_export(
            video_path=video_path,
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
    move_original_video(video_path, output_folder)

    print("\n" + "="*100)
    print(f"COMPLETATO: {os.path.basename(video_path)}")
    print("="*100)
    print(f"Tutti i file sono stati salvati in: {output_folder}")


def main():
    parser = argparse.ArgumentParser(
        description="Taglia automaticamente i silenzi da uno o più video",
        epilog="Esempi:\n"
               "  %(prog)s video.mp4\n"
               "  %(prog)s video1.mp4 video2.mp4 video3.mp4\n"
               "  %(prog)s *.mp4\n"
               "  %(prog)s videos/**/*.mp4\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('input_videos', nargs='+', help='Percorso dei video di input (supporta glob patterns)')
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

    # Espandi i pattern glob e ottieni la lista di video
    video_files = expand_video_files(args.input_videos)

    if not video_files:
        print("Errore: Nessun file video trovato!")
        print(f"Pattern forniti: {args.input_videos}")
        sys.exit(1)

    total_videos = len(video_files)

    # Stampa parametri di avvio
    print("\n" + "="*100)
    print("AUTOVIDEOMAKER")
    print("="*100)
    print(f"Video trovati: {total_videos}")
    for i, vf in enumerate(video_files, 1):
        print(f"  {i}. {os.path.basename(vf)}")
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

    # Statistiche di elaborazione
    successful = 0
    failed = 0
    failed_videos = []

    # ============================================================
    # ELABORA OGNI VIDEO
    # ============================================================
    for idx, video_path in enumerate(video_files, 1):
        try:
            process_single_video(video_path, args, idx, total_videos)
            successful += 1
        except Exception as e:
            failed += 1
            failed_videos.append((video_path, str(e)))
            print(f"\n{'='*100}")
            print(f"ERRORE durante l'elaborazione di {os.path.basename(video_path)}")
            print(f"Errore: {e}")
            print(f"{'='*100}")
            # Continua con il prossimo video

    # ============================================================
    # RIEPILOGO FINALE
    # ============================================================
    print("\n" + "="*100)
    print("RIEPILOGO ELABORAZIONE")
    print("="*100)
    print(f"Totale video: {total_videos}")
    print(f"Elaborati con successo: {successful}")
    print(f"Falliti: {failed}")

    if failed_videos:
        print("\nVideo falliti:")
        for video, error in failed_videos:
            print(f"  - {os.path.basename(video)}: {error}")

    print("="*100)


if __name__ == '__main__':
    main()
