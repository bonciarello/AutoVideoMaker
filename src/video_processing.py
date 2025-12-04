#!/usr/bin/env python3
"""
Flusso 5: Elaborazione Video e Export
Processa il video, genera segmenti, EDL e esporta i risultati.
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from utils import get_video_info


def generate_edl(keep_ranges: List[Tuple[float, float]],
                video_path: str,
                output_edl: str,
                video_info: Dict) -> None:
    """
    Genera un file EDL (Edit Decision List) per Premiere Pro con video e audio.

    :param keep_ranges: Lista di segmenti da mantenere [(start, end), ...]
    :param video_path: Percorso del video originale
    :param output_edl: Percorso output EDL
    :param video_info: Informazioni video da ffprobe
    """
    video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
    audio_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'audio'), None)
    fps = eval(video_stream.get('r_frame_rate', '30/1')) if video_stream else 30.0

    def sec_to_timecode(sec):
        hours = int(sec // 3600)
        minutes = int((sec % 3600) // 60)
        seconds = int(sec % 60)
        frames = int((sec % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    with open(output_edl, 'w') as f:
        f.write("TITLE: Video Processed\n")
        f.write("FCM: NON-DROP FRAME\n\n")

        cumulative = 0
        event_num = 1

        for i, (start, end) in enumerate(keep_ranges, 1):
            source_in = sec_to_timecode(start)
            source_out = sec_to_timecode(end)
            dest_in = sec_to_timecode(cumulative)

            duration = end - start
            cumulative += duration
            dest_out = sec_to_timecode(cumulative)

            clip_name = Path(video_path).name

            # VIDEO TRACK (sempre presente)
            f.write(f"{event_num:03d}  AX       V     C        {source_in} {source_out} {dest_in} {dest_out}\n")
            f.write(f"* FROM CLIP NAME: {clip_name}\n")

            # AUDIO TRACK (se presente)
            if audio_stream:
                event_num += 1
                # Usa A invece di AA per compatibilità con Premiere Pro
                f.write(f"{event_num:03d}  AX       A     C        {source_in} {source_out} {dest_in} {dest_out}\n")
                f.write(f"* FROM CLIP NAME: {clip_name}\n")

            f.write("\n")
            event_num += 1


def cut_video_segments(video_path: str,
                      keep_ranges: List[Tuple[float, float]],
                      chunks_dir: str) -> None:
    """
    Taglia il video in segmenti usando FFmpeg.

    :param video_path: Percorso del video originale
    :param keep_ranges: Lista di segmenti da mantenere [(start, end), ...]
    :param chunks_dir: Directory dove salvare i chunks
    """
    os.makedirs(chunks_dir, exist_ok=True)

    for idx, (start, end) in enumerate(keep_ranges):
        dur = end - start
        c_name = f"c_{idx:04d}.mp4"
        chunk_path = os.path.join(chunks_dir, c_name)

        # Taglia segmento usando -ss e -t con codec copy
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(dur),
            "-c", "copy",
            chunk_path
        ]

        subprocess.run(cmd, check=True)


def calculate_statistics(keep_ranges: List[Tuple[float, float]],
                        video_duration: float) -> Dict[str, float]:
    """
    Calcola statistiche sui tagli effettuati.

    :param keep_ranges: Lista di segmenti mantenuti
    :param video_duration: Durata originale del video
    :return: Dizionario con statistiche
    """
    trimmed_duration = sum(end - start for start, end in keep_ranges)
    saved_time = video_duration - trimmed_duration
    saved_percentage = (saved_time / video_duration * 100) if video_duration > 0 else 0

    return {
        'original_duration': video_duration,
        'trimmed_duration': trimmed_duration,
        'saved_time': saved_time,
        'saved_percentage': saved_percentage,
        'num_segments': len(keep_ranges)
    }


def process_and_export(video_path: str,
                      silence_cuts: List[Tuple[float, float]],
                      ai_cuts: List[Tuple[float, float]],
                      video_duration: float,
                      output_folder: str,
                      video_info: Dict = None,
                      name_no_ext: str = None,
                      transcript_text: str = None,
                      save_transcript: bool = True,
                      vocals_audio_path: str = None) -> Optional[str]:
    """
    Processa ed esporta il video unendo silence_cuts e ai_cuts.

    :param video_path: Percorso del video originale
    :param silence_cuts: Lista di intervalli da tagliare [(start, end), ...]
    :param ai_cuts: Lista di intervalli AI da tagliare [(start, end), ...]
    :param video_duration: Durata totale del video in secondi
    :param output_folder: Cartella di output per i file generati
    :param video_info: Informazioni video da ffprobe (opzionale)
    :param name_no_ext: Nome del file senza estensione (opzionale)
    :param transcript_text: Testo della trascrizione (opzionale)
    :param save_transcript: Se True, salva la trascrizione (default: True)
    :param vocals_audio_path: Percorso audio vocals separato (opzionale, per uso futuro)
    :return: Percorso del file di trascrizione se salvato, altrimenti None
    """
    # 1. Unisci tutti i tagli e ordinali
    all_cuts = silence_cuts + ai_cuts
    all_cuts.sort(key=lambda x: x[0])

    # 2. Unisci intervalli sovrapposti
    merged_cuts = []
    if all_cuts:
        curr_start, curr_end = all_cuts[0]
        for next_start, next_end in all_cuts[1:]:
            if next_start < curr_end:
                curr_end = max(curr_end, next_end)
            else:
                merged_cuts.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged_cuts.append((curr_start, curr_end))

    # 3. Calcola i segmenti da mantenere (inverso dei tagli)
    # Durata minima del segmento in secondi (evita segmenti troppo corti che causano errori in FFmpeg)
    MIN_SEGMENT_DURATION = 0.1

    keep_ranges = []
    current_pos = 0.0
    for cs, ce in merged_cuts:
        duration = cs - current_pos
        if cs > current_pos and duration >= MIN_SEGMENT_DURATION:
            keep_ranges.append((current_pos, cs))
        current_pos = max(current_pos, ce)

    # Aggiungi segmento finale se ha durata sufficiente
    final_duration = video_duration - current_pos
    if final_duration >= MIN_SEGMENT_DURATION:
        keep_ranges.append((current_pos, video_duration))

    # Calcola statistiche
    stats = calculate_statistics(keep_ranges, video_duration)
    print(f"Segmenti: {stats['num_segments']} | Risparmio: {stats['saved_time']:.1f}s ({stats['saved_percentage']:.1f}%)")

    # Ottieni informazioni video se non fornite
    if video_info is None:
        video_info = get_video_info(video_path)

    if name_no_ext is None:
        name_no_ext = Path(video_path).stem

    # Crea cartella output se non esiste
    os.makedirs(output_folder, exist_ok=True)
    chunks_dir = os.path.join(output_folder, "chunks")

    # 4. Genera EDL per Premiere Pro
    edl_path = os.path.join(output_folder, "premiere_pro.edl")
    generate_edl(keep_ranges, video_path, edl_path, video_info)

    # 5. Genera Segmenti
    cut_video_segments(video_path, keep_ranges, chunks_dir)
    print("Segmenti video salvati in:", chunks_dir)

    # 6. Salva trascrizione se disponibile
    if save_transcript and transcript_text:
        txt_path = os.path.join(output_folder, "transcript.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(transcript_text)
        print(f"Trascrizione salvata in: {txt_path}")
        return txt_path  # Ritorna il path della trascrizione per la generazione metadati

    return None


def move_original_video(video_path: str, output_folder: str) -> str:
    """
    Sposta il video originale nella cartella di output.

    :param video_path: Percorso del video originale
    :param output_folder: Cartella di destinazione
    :return: Nuovo percorso del video
    """
    original_video_name = Path(video_path).name
    destination_path = os.path.join(output_folder, original_video_name)

    # Verifica se il video originale non è già nella cartella di output
    if os.path.abspath(video_path) != os.path.abspath(destination_path):
        shutil.move(video_path, destination_path)
        return destination_path

    return video_path


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 4:
        print("Uso: python 5_video_processing.py <video_path> <silence_cuts_json> <output_folder>")
        sys.exit(1)

    import json
    video = sys.argv[1]
    cuts_file = sys.argv[2]
    output = sys.argv[3]

    with open(cuts_file, 'r') as f:
        cuts = json.load(f)

    video_info = get_video_info(video)
    duration = float(video_info['format']['duration'])

    process_and_export(video, cuts, [], duration, output)
    print(f"Export completato in: {output}")
