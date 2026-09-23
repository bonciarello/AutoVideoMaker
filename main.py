#!/usr/bin/env python3
"""
AutoVideoMaker - Main Orchestrator
Analyzes videos, identifies silence portions and generates cut videos with AI metadata.

This is the main file that orchestrates all processing flows:
1. Dependency verification
2. Audio extraction (with AI vocal separation)
3. Silence analysis
4. AI transcription (Deepgram default, Whisper optional)
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
from utils import log_phase, get_video_info, parse_fps
from dependency_check import check_dependencies
from audio_extraction import extract_audio
from silence_analysis import (analyze_audio_silence, merge_silence_intervals,
                              build_speech_segments_from_words, invert_segments)
from transcription import transcribe_audio, load_words_json, save_words_json
from cleanup import run_cleanup, write_report
from cleanup_llm import make_client
from video_processing import process_and_export, move_original_video
from metadata_generation import generate_video_metadata
from capcut_export import generate_capcut_project


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
            else:
                print(f"Attenzione: nessun file trovato per '{pattern}'")

        # Filtra solo i file video
        for match in matches:
            if os.path.isfile(match):
                ext = os.path.splitext(match)[1].lower()
                if ext in video_extensions:
                    video_files.append(os.path.abspath(match))

    # Rimuovi duplicati mantenendo l'ordine (pattern sovrapposti possono
    # selezionare lo stesso file più volte)
    seen = set()
    unique_files = []
    for vf in video_files:
        if vf not in seen:
            seen.add(vf)
            unique_files.append(vf)

    return unique_files


def process_single_video(video_path: str, args: argparse.Namespace, video_num: int = 0, total_videos: int = 1) -> dict:
    """
    Elabora un singolo video.

    :param video_path: Percorso del video
    :param args: Argomenti da linea di comando
    :param video_num: Numero del video corrente (per display)
    :param total_videos: Totale video da elaborare
    :return: Dict con keep_ranges, video_path finale, video_info e markers (per progetto CapCut combinato)
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
    words_path = os.path.join(output_folder, "words.json")

    # ============================================================
    # ANALISI VIDEO INIZIALE
    # ============================================================
    log_phase("Analisi video")
    video_info = get_video_info(video_path)
    video_duration = float(video_info['format']['duration'])
    video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
    fps = parse_fps(video_stream)
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
        # FLUSSO 4: TRASCRIZIONE (con timestamp parola)
        # ============================================================
        # Riusata da words.json se il video e le opzioni sono gli stessi:
        # i rilanci non rifanno la chiamata al servizio di trascrizione.
        if args.no_transcription:
            transcription = {"text": "", "words": []}
        else:
            cached = None if args.retranscribe else load_words_json(
                words_path, video_path, video_duration, args.transcriber, args.language)
            if cached:
                log_phase("Trascrizione (riusata da words.json)")
                print(f"{len(cached['words'])} parole, nessuna nuova trascrizione")
                transcription = cached
            else:
                log_phase(f"Trascrizione ({args.transcriber})")
                transcription = transcribe_audio(
                    audio_path,
                    transcriber=args.transcriber,
                    whisper_model=args.whisper_model,
                    deepgram_model=args.deepgram_model,
                    language=args.language
                )
                if transcription["words"]:
                    save_words_json(words_path, transcription, video_path, video_duration, args.language)
        transcript_text = transcription["text"]
        words = transcription["words"]

        # ============================================================
        # FLUSSO 3: CALCOLO INTERVALLI DA TAGLIARE
        # ============================================================
        # Modalità 'speech': tagli basati sui timestamp delle parole
        # (precisi, non troncano le parole). Modalità 'silence':
        # rilevamento silenzi FFmpeg. 'auto': speech se disponibile.
        use_speech = args.cut_mode == 'speech' or (args.cut_mode == 'auto' and bool(words))

        if use_speech and words:
            log_phase("Segmenti parlati (da trascrizione)")
            speech_segments = build_speech_segments_from_words(
                words,
                max_gap=args.word_gap,
                pad=args.speech_pad,
                video_duration=video_duration
            )
            merged_silence = invert_segments(speech_segments, video_duration)
            print(f"Segmenti parlati: {len(speech_segments)} | Intervalli da rimuovere: {len(merged_silence)}")
        else:
            if args.cut_mode == 'speech' and not words:
                print("Attenzione: timestamp delle parole non disponibili, uso rilevamento silenzi")
            log_phase("Analisi silenzi")
            silence_intervals = analyze_audio_silence(
                audio_path,
                args.threshold,
                args.duration
            )
            merged_silence = merge_silence_intervals(
                silence_intervals,
                args.merge
            )
            print(f"Intervalli da rimuovere: {len(merged_silence)}")

        # ============================================================
        # PULIZIA TAKE (false partenze, ripetizioni, take rifatti)
        # ============================================================
        cleanup_mode = 'off' if args.no_transcription else args.cleanup
        cleanup_result = None
        if cleanup_mode != 'off':
            if words:
                log_phase("Pulizia take")
                if transcription.get("transcriber") == "whisper":
                    print("Attenzione: trascrizione Whisper, le frasi interrotte («...») "
                          "saranno riconosciute raramente")
                client = make_client() if cleanup_mode == 'full' else None
                cleanup_result = run_cleanup(
                    words, mode=cleanup_mode, cue_word=args.cue_word,
                    audio_path=audio_path, video_duration=video_duration,
                    pad=args.speech_pad, client=client
                )
            else:
                print("Pulizia take saltata: nessuna parola trascritta")
        ai_cuts = cleanup_result.time_cuts() if cleanup_result else []
        markers = cleanup_result.markers() if cleanup_result else []

        # Determina nome base per i file
        name_no_ext = Path(video_path).stem + "_tagliato"

        # ============================================================
        # FLUSSO 5: ELABORAZIONE VIDEO E EXPORT
        # ============================================================
        log_phase("Export video e file")
        export_result = process_and_export(
            video_path=video_path,
            silence_cuts=merged_silence,
            ai_cuts=ai_cuts,
            video_duration=video_duration,
            output_folder=output_folder,
            video_info=video_info,
            name_no_ext=name_no_ext,
            transcript_text=transcript_text,
            save_transcript=not args.no_transcription,
            vocals_audio_path=vocals_full_path,
            export_capcut=not args.capcut_single_project,
            markers=markers
        )
        transcript_path = export_result["transcript_path"]
        if cleanup_result:
            write_report(output_folder, Path(video_path).name, cleanup_result, words,
                         export_result["keep_ranges"], video_duration, merged_silence)

        # ============================================================
        # FLUSSO 6: GENERAZIONE METADATI AI
        # ============================================================
        if transcript_path and not args.no_transcription and not args.no_metadata:
            generate_video_metadata(transcript_path, output_folder)

    # ============================================================
    # SPOSTA VIDEO ORIGINALE
    # ============================================================
    # process_and_export ha già spostato il video (prima di generare il
    # progetto CapCut, che deve linkare il percorso finale). Qui si usa il
    # percorso risultante senza spostare di nuovo.
    final_video_path = export_result.get("video_path") or video_path
    if os.path.abspath(final_video_path) != os.path.abspath(os.path.join(output_folder, Path(video_path).name)):
        final_video_path = move_original_video(video_path, output_folder)

    print("\n" + "="*100)
    print(f"COMPLETATO: {os.path.basename(video_path)}")
    print("="*100)
    print(f"Tutti i file sono stati salvati in: {output_folder}")

    return {
        "keep_ranges": export_result["keep_ranges"],
        "video_path": final_video_path,
        "video_info": video_info,
        "markers": markers
    }


def build_parser() -> argparse.ArgumentParser:
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
    parser.add_argument('--transcriber', type=str, default='deepgram',
                       choices=['deepgram', 'whisper'],
                       help='Servizio di trascrizione (default: deepgram, richiede DEEPGRAM_API_KEY nel file .env; fallback automatico a Whisper)')
    parser.add_argument('--whisper-model', type=str, default='medium',
                       choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='Modello Whisper per la trascrizione (default: medium)')
    parser.add_argument('--deepgram-model', type=str, default='nova-3',
                       help='Modello Deepgram per la trascrizione, es. nova-3, nova-2, enhanced (default: nova-3)')
    parser.add_argument('--language', type=str, default='it',
                       help='Lingua della trascrizione (default: it)')
    parser.add_argument('--cut-mode', type=str, default='auto',
                       choices=['auto', 'speech', 'silence'],
                       help="Metodo di taglio: 'speech' usa i timestamp delle parole dalla trascrizione "
                            "(più preciso, non tronca le parole), 'silence' usa il rilevamento silenzi "
                            "FFmpeg, 'auto' usa speech quando disponibile (default: auto)")
    parser.add_argument('--word-gap', type=float, default=0.2,
                       help='Pausa massima tra parole nello stesso segmento parlato in secondi (default: 0.2). '
                            'Pause piu lunghe vengono tagliate.')
    parser.add_argument('--speech-pad', type=float, default=0.05,
                       help='Margine di sicurezza ai bordi dei segmenti parlati in secondi (default: 0.05). '
                            'Il silenzio residuo dopo ogni taglio vale 2*questo valore.')
    parser.add_argument('--no-transcription', '--no-whisper', dest='no_transcription',
                       action='store_true',
                       help='Salta la trascrizione e la generazione di metadati AI')
    parser.add_argument('--capcut-single-project', action='store_true',
                       help='Con più video, genera UN solo progetto CapCut con tutte le clip '
                            'in sequenza sulla stessa timeline (invece di un progetto per video)')
    parser.add_argument('--capcut-name', type=str, default=None,
                       help='Nome del progetto CapCut combinato (default: nome del primo video)')
    parser.add_argument('--cleanup', type=str, default='full', choices=['full', 'rules', 'off'],
                       help="Pulizia take: 'full' regole + Claude (richiede ANTHROPIC_API_KEY), "
                            "'rules' solo regole (gratis), 'off' solo pause (default: full)")
    parser.add_argument('--cue-word', type=str, default='rifaccio',
                       help="Parola-segnale detta da sola tra due pause per scartare il take appena "
                            "sbagliato (default: rifaccio; stringa vuota per disattivarla)")
    parser.add_argument('--retranscribe', action='store_true',
                       help='Ignora words.json e rifà la trascrizione')
    parser.add_argument('--no-metadata', action='store_true',
                       help='Salta titolo, descrizione e miniatura AI (utile per i rilanci di prova)')
    return parser


def main():
    parser = build_parser()

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
    if not args.no_transcription:
        print(f"Transcriber: {args.transcriber}")
        if args.transcriber == 'whisper':
            print(f"Whisper model: {args.whisper_model}")
        print(f"Lingua: {args.language}")
    else:
        print("Trascrizione: DISABLED")
    print(f"Cut mode: {args.cut_mode}")
    if args.cut_mode != 'silence':
        print(f"Word gap: {args.word_gap}s | Speech pad: {args.speech_pad}s")
    if not args.no_transcription:
        cue = f" | parola-segnale: «{args.cue_word}»" if args.cue_word and args.cleanup != 'off' else ""
        print(f"Pulizia take: {args.cleanup}{cue}")
        if args.no_metadata:
            print("Metadati AI: DISABLED")
    if args.capcut_single_project:
        print("CapCut: progetto combinato unico")
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
    capcut_clips = []  # Clip per il progetto CapCut combinato

    # ============================================================
    # ELABORA OGNI VIDEO
    # ============================================================
    for idx, video_path in enumerate(video_files, 1):
        try:
            clip_info = process_single_video(video_path, args, idx, total_videos)
            if clip_info:
                capcut_clips.append(clip_info)
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
    # PROGETTO CAPCUT COMBINATO (tutte le clip su una timeline)
    # ============================================================
    if args.capcut_single_project and capcut_clips:
        log_phase("Progetto CapCut combinato")
        project_name = args.capcut_name or Path(capcut_clips[0]["video_path"]).stem
        try:
            generate_capcut_project(capcut_clips, project_name=project_name)
        except Exception as e:
            print(f"Attenzione: generazione progetto CapCut combinato fallita: {e}")

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
