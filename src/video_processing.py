#!/usr/bin/env python3
"""
Flusso 5: Elaborazione Video e Export
Processa il video, genera segmenti, EDL e esporta i risultati.
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from utils import get_video_info, parse_fps
from capcut_export import generate_capcut_project


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
    fps = parse_fps(video_stream)

    # Canali audio della sorgente
    audio_channels = 0
    if audio_stream:
        try:
            audio_channels = int(audio_stream.get('channels', 2))
        except (TypeError, ValueError):
            audio_channels = 2

    # Designazione traccia CMX 3600 COMBINATA (video + audio nello stesso evento).
    # Fondamentale per Premiere Pro: con eventi V e A separati, l'import EDL
    # linka spesso solo il video e scarta gli eventi audio standalone.
    #   AA/V = audio stereo (canali 1&2) + video
    #   A/V  = audio mono (canale 1) + video
    #   V    = solo video
    if audio_channels >= 2:
        track_type = 'AA/V'
    elif audio_channels == 1:
        track_type = 'A/V'
    else:
        track_type = 'V'

    def sec_to_timecode(sec):
        hours = int(sec // 3600)
        minutes = int((sec % 3600) // 60)
        seconds = int(sec % 60)
        frames = int((sec % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    clip_name = Path(video_path).name

    with open(output_edl, 'w') as f:
        f.write("TITLE: Video Processed\n")
        f.write("FCM: NON-DROP FRAME\n\n")

        cumulative = 0

        for event_num, (start, end) in enumerate(keep_ranges, 1):
            source_in = sec_to_timecode(start)
            source_out = sec_to_timecode(end)
            dest_in = sec_to_timecode(cumulative)

            duration = end - start
            cumulative += duration
            dest_out = sec_to_timecode(cumulative)

            # Evento combinato video+audio: un taglio = una riga.
            # Campo traccia a 5 caratteri (col 15-19) per l'allineamento CMX 3600.
            f.write(f"{event_num:03d}  AX       {track_type:<5} C        {source_in} {source_out} {dest_in} {dest_out}\n")
            f.write(f"* FROM CLIP NAME: {clip_name}\n\n")

    print(f"EDL generato: {len(keep_ranges)} eventi, traccia {track_type}")


def validate_edl(edl_path: str) -> List[str]:
    """
    Verifica la struttura di un file EDL (header, eventi, timecode, continuità).

    :param edl_path: Percorso del file EDL da verificare
    :return: Lista di problemi trovati (vuota se il file è valido)
    """
    problems = []

    with open(edl_path, 'r') as f:
        lines = f.readlines()

    if not lines:
        return ["File EDL vuoto"]

    if not lines[0].startswith("TITLE:"):
        problems.append("Riga TITLE mancante")
    if len(lines) < 2 or not lines[1].startswith("FCM:"):
        problems.append("Riga FCM mancante")

    tc_pattern = re.compile(r'^(\d{2}):(\d{2}):(\d{2}):(\d{2})$')

    def tc_to_frames(tc):
        m = tc_pattern.match(tc)
        if not m:
            return None
        h, mnt, s, fr = map(int, m.groups())
        return ((h * 3600) + (mnt * 60) + s) * 100 + fr  # confronto relativo

    events = []
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip('\n')
        if not stripped or stripped.startswith(('TITLE:', 'FCM:', '*')):
            continue

        parts = stripped.split()
        if len(parts) < 8:
            problems.append(f"Riga {i}: evento malformato ({len(parts)} campi)")
            continue

        event_id, reel, track, edit = parts[0], parts[1], parts[2], parts[3]
        src_in, src_out, dst_in, dst_out = parts[4], parts[5], parts[6], parts[7]

        if not event_id.isdigit():
            problems.append(f"Riga {i}: numero evento non numerico '{event_id}'")
        if track not in ('V', 'A', 'A2', 'AA', 'B', 'A/V', 'A2/V', 'AA/V'):
            problems.append(f"Riga {i}: tipo traccia non standard '{track}'")
        if edit != 'C':
            problems.append(f"Riga {i}: transizione '{edit}' non supportata (attesa 'C')")

        for label, tc in [('source_in', src_in), ('source_out', src_out),
                          ('dest_in', dst_in), ('dest_out', dst_out)]:
            if tc_to_frames(tc) is None:
                problems.append(f"Riga {i}: timecode {label} malformato '{tc}'")

        if tc_to_frames(src_in) is not None and tc_to_frames(src_out) is not None:
            if tc_to_frames(src_out) <= tc_to_frames(src_in):
                problems.append(f"Riga {i}: source_out <= source_in")

        events.append((event_id, dst_in, dst_out))

    if not events:
        problems.append("Nessun evento trovato nel file EDL")
    else:
        # Verifica numerazione progressiva e continuità della timeline di destinazione
        for idx, (event_id, dst_in, dst_out) in enumerate(events, 1):
            if int(event_id) != idx:
                problems.append(f"Numerazione eventi non progressiva: atteso {idx}, trovato {event_id}")
            if idx > 1 and tc_to_frames(dst_in) is not None:
                prev_dst_out = tc_to_frames(events[idx - 2][2])
                if tc_to_frames(dst_in) != prev_dst_out:
                    problems.append(f"Evento {event_id}: dest_in non contiguo (buco/sovrapposizione nella timeline)")

    return problems


def cut_video_segments(video_path: str,
                      keep_ranges: List[Tuple[float, float]],
                      chunks_dir: str,
                      vocals_audio_path: str = None) -> None:
    """
    Taglia il video in segmenti usando FFmpeg.

    :param video_path: Percorso del video originale
    :param keep_ranges: Lista di segmenti da mantenere [(start, end), ...]
    :param chunks_dir: Directory dove salvare i chunks
    :param vocals_audio_path: Percorso audio vocals separato (opzionale).
           Se fornito, sostituisce la traccia audio originale nei chunk
           con la voce ripulita dal rumore di fondo.
    """
    os.makedirs(chunks_dir, exist_ok=True)

    use_vocals = bool(vocals_audio_path) and os.path.exists(vocals_audio_path)
    if vocals_audio_path and not use_vocals:
        print(f"Attenzione: file vocals non trovato ({vocals_audio_path}), uso audio originale")

    for idx, (start, end) in enumerate(keep_ranges):
        dur = end - start
        c_name = f"c_{idx:04d}.mp4"
        chunk_path = os.path.join(chunks_dir, c_name)

        if use_vocals:
            # Video in copy dalla sorgente + audio vocals ripulito (ricodificato in AAC)
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", str(start),
                "-i", video_path,
                "-ss", str(start),
                "-i", vocals_audio_path,
                "-t", str(dur),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                chunk_path
            ]
        else:
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
                      vocals_audio_path: str = None,
                      export_capcut: bool = True) -> Dict:
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
    :param vocals_audio_path: Percorso audio vocals separato (opzionale). Se fornito,
           i chunk video useranno la voce ripulita al posto dell'audio originale
    :param export_capcut: Se True, genera il progetto CapCut per questo video
           (default: True). Mettere False in modalità progetto combinato.
    :return: Dict con "transcript_path" (o None) e "keep_ranges" (segmenti mantenuti)
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

    # 4. Genera EDL per Premiere Pro e verifica la struttura
    edl_path = os.path.join(output_folder, "premiere_pro.edl")
    generate_edl(keep_ranges, video_path, edl_path, video_info)
    edl_problems = validate_edl(edl_path)
    if edl_problems:
        print("Attenzione: problemi nel file EDL:")
        for problem in edl_problems:
            print(f"  - {problem}")

    # 4b. Genera i chunk video (con audio vocals ripulito, se disponibile).
    # Va fatto PRIMA di spostare il video originale: ffmpeg legge dal
    # percorso di input originale.
    cut_video_segments(video_path, keep_ranges, chunks_dir, vocals_audio_path)
    print("Segmenti video salvati in:", chunks_dir)

    # 4c. Sposta il video originale nella cartella di output, poi genera il
    # progetto CapCut puntando alla posizione FINALE. Se il progetto linkasse
    # un file inesistente, CapCut mostrerebbe le clip vuote o da 0.
    final_video_path = move_original_video(video_path, output_folder)
    if export_capcut:
        try:
            generate_capcut_project(
                clips=[{
                    "keep_ranges": keep_ranges,
                    "video_path": final_video_path,
                    "video_info": video_info
                }],
                project_name=Path(video_path).stem
            )
        except Exception as e:
            print(f"Attenzione: generazione progetto CapCut fallita: {e}")

    # 6. Salva trascrizione se disponibile
    transcript_path = None
    if save_transcript and transcript_text:
        transcript_path = os.path.join(output_folder, "transcript.txt")
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript_text)
        print(f"Trascrizione salvata in: {transcript_path}")

    return {"transcript_path": transcript_path, "keep_ranges": keep_ranges,
            "video_path": final_video_path}


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
    if os.path.abspath(video_path) == os.path.abspath(destination_path):
        return video_path

    # Non sovrascrivere un file esistente: se la destinazione esiste già,
    # lascia il video originale al suo posto
    if os.path.exists(destination_path):
        print(f"Attenzione: esiste già {destination_path}, il video originale non verrà spostato.")
        return video_path

    try:
        shutil.move(video_path, destination_path)
        return destination_path
    except (OSError, shutil.Error) as e:
        print(f"Attenzione: impossibile spostare il video originale: {e}")
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
