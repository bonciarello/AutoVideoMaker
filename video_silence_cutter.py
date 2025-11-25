#!/usr/bin/env python3
"""
Video Silence Cutter
Analizza un video, identifica le parti di silenzio e genera un progetto CapCut con i tagli.
"""

import os
import json
import argparse
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Tuple, Dict
import numpy as np
from datetime import datetime
import uuid


def check_dependencies():
    """Verifica che ffmpeg sia installato."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("ffmpeg non è installato. Installalo con: brew install ffmpeg (macOS) o apt-get install ffmpeg (Linux)")


def extract_audio(video_path: str, output_audio: str, noise_reduction: bool = True) -> None:
    """Estrae l'audio dal video con riduzione del rumore opzionale."""
    if noise_reduction:
        print("🎵 Estraendo e ripulendo audio...", end='', flush=True)
        # Filtro audio complesso per ridurre il rumore di fondo
        audio_filter = (
            "highpass=f=200,"           # Rimuove rumori bassi (< 200Hz)
            "lowpass=f=3000,"            # Rimuove rumori alti (> 3000Hz) - mantiene voce umana
            "afftdn=nf=-25,"             # FFT denoiser - riduce rumore
            "anlmdn=s=0.00001:p=0.002:r=0.002,"  # Non-local means denoiser
            "loudnorm"                   # Normalizza il volume
        )
    else:
        print("🎵 Estraendo audio...", end='', flush=True)
        audio_filter = None

    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1'
    ]

    if audio_filter:
        cmd.extend(['-af', audio_filter])

    cmd.extend(['-y', output_audio])

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(" ✓")


def analyze_audio_silence(audio_path: str, silence_threshold_db: float = -40,
                         min_silence_duration: float = 0.5) -> List[Tuple[float, float]]:
    """Analizza l'audio e trova gli intervalli di silenzio usando ffmpeg."""
    print(f"🔍 Rilevando silenzi (soglia: {silence_threshold_db}dB)...", end='', flush=True)

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

    print(f" ✓ ({len(silence_intervals)} intervalli)")
    return silence_intervals


def generate_subtitles_whisper(video_path: str, output_srt: str = None, words_per_segment: int = 4, model_size: str = "medium") -> List[Dict]:
    """
    Genera sottotitoli usando Whisper con segmenti di N parole.

    :param video_path: Percorso del video
    :param output_srt: Percorso output SRT (opzionale, per file temporaneo)
    :param words_per_segment: Numero di parole per segmento (default: 4)
    :param model_size: Dimensione del modello Whisper (tiny, base, small, medium, large, default: medium)
    :return: Lista di segmenti sottotitoli
    """
    try:
        import whisper
        print(f"🎤 Generando sottotitoli con Whisper {model_size} (segmenti di ~{words_per_segment} parole)...")

        model = whisper.load_model(model_size)
        # Usa word_timestamps per ottenere timestamp parola per parola
        result = model.transcribe(video_path, language="it", word_timestamps=True)

        segments = []

        # Se Whisper supporta word_timestamps, dividi ogni N parole
        for segment in result['segments']:
            # Controlla se ci sono word timestamps disponibili
            if 'words' in segment and segment['words']:
                words = segment['words']

                # Dividi le parole in gruppi di N
                for i in range(0, len(words), words_per_segment):
                    word_group = words[i:i + words_per_segment]

                    if word_group:
                        # Prendi il timestamp della prima e ultima parola del gruppo
                        start_time = word_group[0].get('start', word_group[0].get('timestamp', segment['start']))
                        end_time = word_group[-1].get('end', word_group[-1].get('timestamp', segment['end']))

                        # Se end_time non è disponibile, stima dalla durata media
                        if end_time == start_time or end_time is None:
                            # Stima la durata basandosi sul numero di caratteri
                            text_group = ' '.join([w.get('word', w.get('text', '')).strip() for w in word_group])
                            estimated_duration = len(text_group) * 0.05  # ~50ms per carattere
                            end_time = start_time + estimated_duration
                        else:
                            text_group = ' '.join([w.get('word', w.get('text', '')).strip() for w in word_group])

                        segments.append({
                            'start': float(start_time),
                            'end': float(end_time),
                            'text': text_group.strip()
                        })
            else:
                # Fallback: usa i segmenti originali se word_timestamps non disponibile
                # e dividi il testo manualmente
                text = segment['text'].strip()
                words = text.split()
                duration = segment['end'] - segment['start']
                words_count = len(words)

                if words_count > 0:
                    time_per_word = duration / words_count

                    for i in range(0, len(words), words_per_segment):
                        word_group = words[i:i + words_per_segment]
                        group_start = segment['start'] + (i * time_per_word)
                        group_end = segment['start'] + ((i + len(word_group)) * time_per_word)

                        segments.append({
                            'start': float(group_start),
                            'end': float(group_end),
                            'text': ' '.join(word_group)
                        })

        print(f"✓ Trascrizione completata: {len(segments)} segmenti (~{words_per_segment} parole ciascuno)")

        # Salva file SRT temporaneo solo se richiesto
        if output_srt:
            with open(output_srt, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    f.write(f"{i}\n")
                    f.write(f"{format_timestamp_srt(segment['start'])} --> {format_timestamp_srt(segment['end'])}\n")
                    f.write(f"{segment['text']}\n\n")
            print(f"  (File temporaneo SRT: {output_srt})")

        return segments
    except ImportError:
        print("ATTENZIONE: openai-whisper non è installato. Installalo con: pip install openai-whisper")
        return []


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

    print(f"✓ Sottotitoli JSON generati: {output_json}")


def save_subtitles_txt(segments: List[Dict], output_txt: str) -> None:
    """Salva i sottotitoli in formato TXT (solo testo trascritto)."""
    with open(output_txt, 'w', encoding='utf-8') as f:
        for segment in segments:
            f.write(f"{segment['text']}\n")

    print(f"✓ Trascrizione TXT generata: {output_txt}")


def format_timestamp_srt(seconds: float) -> str:
    """Formatta i secondi in formato timestamp SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def get_video_info(video_path: str) -> Dict:
    """Ottiene informazioni sul video usando ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_format', '-show_streams',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def merge_silence_intervals(silence_intervals: List[Tuple[float, float]],
                           subtitle_segments: List[Dict],
                           merge_distance: float = 1.0) -> List[Tuple[float, float]]:
    """Unisce gli intervalli di silenzio e considera anche le pause tra sottotitoli."""
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
    """Calcola i segmenti da mantenere (inverso dei silenzi)."""
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


def export_cut_video(video_path: str, kept_segments: List[Tuple[float, float]],
                    output_video: str, video_info: Dict = None) -> None:
    """Esporta il video tagliato usando taglio fisico + concatenazione (identico al CCP)."""
    print(f"\nGenerando video tagliato in {output_video}...")

    # Ottieni info video se non fornite
    if video_info is None:
        video_info = get_video_info(video_path)

    # Crea directory temporanea per i segmenti
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp(prefix='video_export_segments_')

    try:
        segment_files = []
        total_segments = len(kept_segments)
        start_time = time.time()

        print(f"\n📹 Tagliando {total_segments} segmenti video...")

        # Taglia ogni segmento fisicamente
        for i, (start, end) in enumerate(kept_segments):
            duration = end - start
            segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp4")

            # Taglia usando FFmpeg con codec copy
            cmd = [
                'ffmpeg',
                '-ss', str(start),
                '-i', video_path,
                '-t', str(duration),
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                '-y',
                segment_path
            ]

            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            segment_files.append(segment_path)

            # Calcola progresso e tempo rimanente
            progress = ((i + 1) / total_segments) * 100
            elapsed_time = time.time() - start_time
            avg_time_per_segment = elapsed_time / (i + 1)
            remaining_segments = total_segments - (i + 1)
            eta_seconds = avg_time_per_segment * remaining_segments

            # Formatta ETA
            if eta_seconds < 60:
                eta_str = f"{int(eta_seconds)}s"
            else:
                eta_min = int(eta_seconds // 60)
                eta_sec = int(eta_seconds % 60)
                eta_str = f"{eta_min}m {eta_sec}s"

            # Barra di progresso
            bar_length = 30
            filled_length = int(bar_length * (i + 1) / total_segments)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)

            # Stampa barra (sovrascrive la riga)
            print(f"\r  [{bar}] {progress:.1f}% | {i+1}/{total_segments} | ETA: {eta_str}  ", end='', flush=True)

        print()  # Nuova riga

        # Concatena i segmenti usando il concat demuxer di FFmpeg
        print("🔗 Concatenando segmenti...", end='', flush=True)

        # Crea file di lista per concat
        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, 'w') as f:
            for segment_file in segment_files:
                f.write(f"file '{segment_file}'\n")

        # Concatena usando concat demuxer
        cmd_concat = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_path,
            '-c', 'copy',
            '-y',
            output_video
        ]

        subprocess.run(
            cmd_concat,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        print(" ✓")
        print(f"✓ Video salvato: {output_video}")

    finally:
        # Pulizia file temporanei
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


def process_and_export(video_path: str, silence_cuts: List[Tuple[float, float]],
                      ai_cuts: List[Tuple[float, float]], video_duration: float,
                      output_folder: str, video_info: Dict = None, name_no_ext: str = None,
                      subtitle_segments: List[Dict] = None, save_subtitles: bool = True) -> None:
    """
    Processa ed esporta il video unendo silence_cuts e ai_cuts.

    :param video_path: Percorso del video originale
    :param silence_cuts: Lista di intervalli da tagliare [(start, end), ...]
    :param ai_cuts: Lista di intervalli AI da tagliare [(start, end), ...]
    :param video_duration: Durata totale del video in secondi
    :param output_folder: Cartella di output per i file generati
    :param video_info: Informazioni video da ffprobe (opzionale)
    :param name_no_ext: Nome del file senza estensione (opzionale)
    :param subtitle_segments: Segmenti sottotitoli già generati (opzionale)
    :param save_subtitles: Se True, salva i sottotitoli (default: True)
    """
    print("\n" + "="*60)
    print("--> 3. Calcolo Timeline...")
    print("="*60)

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

    print(f"  Tagli silenzi: {len(silence_cuts)}")
    print(f"  Tagli AI: {len(ai_cuts)}")
    print(f"  Tagli uniti: {len(merged_cuts)}")

    # 3. Calcola i segmenti da mantenere (inverso dei tagli)
    keep_ranges = []
    current_pos = 0.0
    for cs, ce in merged_cuts:
        if cs > current_pos and (cs - current_pos) > 0.1:
            keep_ranges.append((current_pos, cs))
        current_pos = max(current_pos, ce)

    if current_pos < video_duration:
        keep_ranges.append((current_pos, video_duration))

    print(f"  Segmenti da mantenere: {len(keep_ranges)}")

    # Calcola statistiche
    original_duration = video_duration
    trimmed_duration = sum(end - start for start, end in keep_ranges)
    saved_time = original_duration - trimmed_duration

    print(f"\n  Durata originale: {original_duration:.2f}s")
    print(f"  Durata finale: {trimmed_duration:.2f}s")
    print(f"  Tempo risparmiato: {saved_time:.2f}s ({saved_time/original_duration*100:.1f}%)")

    # Ottieni informazioni video se non fornite
    if video_info is None:
        video_info = get_video_info(video_path)

    if name_no_ext is None:
        name_no_ext = Path(video_path).stem

    # Crea cartella output se non esiste
    os.makedirs(output_folder, exist_ok=True)
    chunks_dir = os.path.join(output_folder, "chunks")
    os.makedirs(chunks_dir, exist_ok=True)

    # 4. Genera EDL per Premiere Pro
    edl_path = os.path.join(output_folder, f"{name_no_ext}.edl")
    generate_edl(keep_ranges, video_path, edl_path, video_info)

    # 5. Genera Video Bozza
    print("\n" + "="*60)
    print("--> 5. Generazione Video Bozza")
    print("="*60)
    print(f"📹 Tagliando {len(keep_ranges)} segmenti...")

    concat_path = os.path.join(output_folder, "concat_list.txt")
    start_time = time.time()

    with open(concat_path, "w") as f:
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
            f.write(f"file 'chunks/{c_name}'\n")

            # Barra di progresso
            progress = ((idx + 1) / len(keep_ranges)) * 100
            elapsed = time.time() - start_time
            avg_time = elapsed / (idx + 1)
            eta = avg_time * (len(keep_ranges) - (idx + 1))

            if eta < 60:
                eta_str = f"{int(eta)}s"
            else:
                eta_str = f"{int(eta // 60)}m {int(eta % 60)}s"

            bar_length = 30
            filled = int(bar_length * (idx + 1) / len(keep_ranges))
            bar = '█' * filled + '░' * (bar_length - filled)

            print(f"\r  [{bar}] {progress:.1f}% | {idx+1}/{len(keep_ranges)} | ETA: {eta_str}  ",
                  end='', flush=True)

    print()  # Nuova riga

    # Concatena i segmenti
    print("🔗 Concatenando segmenti...", end='', flush=True)
    draft = os.path.join(output_folder, f"FINAL_{name_no_ext}.mp4")

    cmd_concat = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", concat_path,
        "-c", "copy",
        draft
    ]

    subprocess.run(cmd_concat, check=True)
    print(" ✓")

    # 6. Salva sottotitoli se disponibili
    if save_subtitles and subtitle_segments:
        print("\n" + "="*60)
        print("--> 6. Salvataggio Sottotitoli")
        print("="*60)

        # Salva in formato SRT
        srt_path = os.path.join(output_folder, f"{name_no_ext}.srt")
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(subtitle_segments, 1):
                f.write(f"{i}\n")
                f.write(f"{format_timestamp_srt(segment['start'])} --> {format_timestamp_srt(segment['end'])}\n")
                f.write(f"{segment['text']}\n\n")
        print(f"  ✓ Sottotitoli SRT salvati: {srt_path}")

        # Verifica che il file esista
        if os.path.exists(srt_path):
            file_size = os.path.getsize(srt_path)
            print(f"     File SRT verificato: {file_size} bytes")

        # Salva in formato JSON
        json_path = os.path.join(output_folder, f"{name_no_ext}_subtitles.json")
        save_subtitles_json(subtitle_segments, json_path, video_path)

        # Verifica che il file esista
        if os.path.exists(json_path):
            file_size = os.path.getsize(json_path)
            print(f"     File JSON verificato: {file_size} bytes")

        # Salva in formato TXT
        txt_path = os.path.join(output_folder, f"{name_no_ext}_transcript.txt")
        save_subtitles_txt(subtitle_segments, txt_path)

        # Verifica che il file esista
        if os.path.exists(txt_path):
            file_size = os.path.getsize(txt_path)
            print(f"     File TXT verificato: {file_size} bytes")

    print(f"\n{'='*60}")
    print(f"✓ Elaborazione completata!")
    print(f"{'='*60}")
    print(f"    [OK] Chunks: {chunks_dir} ({len(keep_ranges)} file)")
    print(f"    [OK] EDL: {edl_path}")
    print(f"    [OK] Video Finale: {draft}")
    if save_subtitles and subtitle_segments:
        print(f"    [OK] Sottotitoli SRT: {os.path.join(output_folder, f'{name_no_ext}.srt')}")
        print(f"    [OK] Sottotitoli JSON: {os.path.join(output_folder, f'{name_no_ext}_subtitles.json')}")
        print(f"    [OK] Trascrizione TXT: {os.path.join(output_folder, f'{name_no_ext}_transcript.txt')}")
    print(f"{'='*60}\n")


def generate_edl(keep_ranges: List[Tuple[float, float]], video_path: str,
                output_edl: str, video_info: Dict) -> None:
    """Genera un file EDL (Edit Decision List) per Premiere Pro con video e audio."""
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

    print(f"  ✓ EDL salvato: {output_edl} (Video + Audio)")


def generate_edl_file(video_path: str, kept_segments: List[Tuple[float, float]],
                     output_edl: str, fps: float = 30.0) -> None:
    """Genera un file EDL (Edit Decision List) per editor video professionali con video e audio."""
    print(f"\nGenerando file EDL in {output_edl}...")

    # Ottieni info video per verificare presenza audio
    try:
        video_info = get_video_info(video_path)
        has_audio = any(s['codec_type'] == 'audio' for s in video_info['streams'])
    except:
        has_audio = True  # Assume audio presente per retrocompatibilità

    def sec_to_timecode(sec):
        hours = int(sec // 3600)
        minutes = int((sec % 3600) // 60)
        seconds = int(sec % 60)
        frames = int((sec % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    with open(output_edl, 'w') as f:
        f.write("TITLE: Video Silence Cutter\n")
        f.write("FCM: NON-DROP FRAME\n\n")

        cumulative = 0
        event_num = 1

        for i, (start, end) in enumerate(kept_segments, 1):
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

            # AUDIO TRACK (se disponibile)
            if has_audio:
                event_num += 1
                f.write(f"{event_num:03d}  AX       A     C        {source_in} {source_out} {dest_in} {dest_out}\n")
                f.write(f"* FROM CLIP NAME: {clip_name}\n")

            f.write("\n")
            event_num += 1

    print(f"✓ File EDL salvato in {output_edl} (Video + Audio)")


def generate_capcut_project(video_path: str, kept_segments: List[Tuple[float, float]],
                           output_path: str, video_info: Dict) -> None:
    """Genera una cartella progetto CapCut con i tagli applicati usando pyJianYingDraft."""

    # Se output_path ha estensione .ccp, rimuovila (serve una cartella)
    if output_path.endswith('.ccp'):
        output_path = output_path[:-4]

    print(f"\nGenerando progetto CapCut in {output_path}...")

    # Usa il wrapper CapCutAPI per creare il progetto
    try:
        from capcut_wrapper import create_capcut_project_with_cuts

        # Determina nome progetto e directory padre
        project_name = Path(output_path).name
        capcut_dir = str(Path(output_path).parent)

        # Crea progetto con pyJianYingDraft
        actual_project_path = create_capcut_project_with_cuts(
            video_path=video_path,
            kept_segments=kept_segments,
            video_info=video_info,
            project_name=project_name,
            capcut_dir=capcut_dir
        )

        # Aggiorna output_path con il path effettivo
        output_path = actual_project_path

        original_duration = float(video_info['format']['duration'])
        trimmed_duration = sum(end - start for start, end in kept_segments)
        saved_time = original_duration - trimmed_duration

        print(f"✓ Progetto CapCut creato con pyJianYingDraft!")
        print(f"  Percorso: {output_path}")
        print(f"  Durata originale: {original_duration:.2f}s")
        print(f"  Segmenti video: {len(kept_segments)}")
        print(f"  Tempo risparmiato: {saved_time:.2f}s ({saved_time/original_duration*100:.1f}%)")

        # Controlla se è nella directory di CapCut
        capcut_dir_check = str(Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft")
        if output_path.startswith(capcut_dir_check):
            print(f"\n✨ Il progetto apparirà automaticamente in CapCut Desktop!")
            print(f"   Apri CapCut e troverai il progetto '{Path(output_path).name}' nella lista")
            print(f"   Il video è già tagliato nella timeline!")
        else:
            print(f"\nImporta in CapCut: File → Open Project → '{Path(output_path).name}'")

        return

    except ImportError as e:
        print(f"⚠️  pyJianYingDraft non disponibile: {e}")
        print("   Uso fallback modalità basica...")
    except Exception as e:
        print(f"⚠️  Errore con pyJianYingDraft: {e}")
        print("   Uso fallback modalità basica...")

    # FALLBACK: Crea struttura basica senza pyJianYingDraft
    _generate_capcut_basic_fallback(video_path, kept_segments, output_path, video_info)


def _generate_capcut_basic_fallback(video_path: str, kept_segments: List[Tuple[float, float]],
                                    output_path: str, video_info: Dict) -> None:
    """Fallback: crea struttura basica CapCut senza pyJianYingDraft"""

    # Crea la cartella del progetto
    os.makedirs(output_path, exist_ok=True)

    # Ottieni informazioni video
    video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
    width = int(video_stream.get('width', 1920)) if video_stream else 1920
    height = int(video_stream.get('height', 1080)) if video_stream else 1080
    fps = float(eval(video_stream.get('r_frame_rate', '30/1'))) if video_stream else 30.0

    draft_id = str(uuid.uuid4()).upper()
    current_time_ms = int(datetime.now().timestamp() * 1000000)

    # draft_info.json - File principale del progetto (basato su struttura reale CapCut)
    draft_info = {
        "canvas_config": {
            "background": None,
            "height": height,
            "ratio": "original",
            "width": width
        },
        "color_space": -1,
        "config": {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 1,
            "export_range": None,
            "maintrack_adsorb": True,
            "material_save_mode": 0,
            "subtitle_recognition_id": "",
            "subtitle_sync": True,
            "video_mute": False
        },
        "cover": None,
        "create_time": 0,
        "draft_type": "video",
        "duration": 0,
        "extra_info": None,
        "fps": fps,
        "free_render_index_mode_on": False,
        "id": draft_id,
        "materials": {
            "videos": [],
            "audios": [],
            "texts": [],
            "stickers": [],
            "effects": [],
            "transitions": [],
            "filters": [],
            "speeds": [],
            "time_marks": [],
            "beats": [],
            "placeholders": [],
            "images": [],
            "canvases": [],
            "audio_effects": [],
            "video_effects": [],
            "audio_fades": [],
            "shapes": []
        },
        "name": "",
        "new_version": "147.0.0",
        "path": "",
        "platform": {
            "app_id": 359289,
            "app_source": "cc",
            "app_version": "7.4.0",
            "os": "mac"
        },
        "relationships": [],
        "tracks": [],
        "update_time": 0,
        "version": 360000
    }

    # draft_meta_info.json
    draft_meta_info = {
        "cloud_draft_cover": True,
        "cloud_draft_sync": True,
        "cloud_package_completed_time": "",
        "draft_cloud_capcut_purchase_info": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_package_type": "",
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "",
        "draft_deeplink_url": "",
        "draft_enterprise_info": {
            "draft_enterprise_extra": "",
            "draft_enterprise_id": "",
            "draft_enterprise_name": "",
            "enterprise_material": []
        },
        "draft_fold_path": os.path.abspath(output_path),
        "draft_id": draft_id,
        "draft_is_ae_produce": False,
        "draft_is_ai_packaging_used": False,
        "draft_is_ai_shorts": False,
        "draft_is_ai_translate": False,
        "draft_is_article_video_draft": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_from_deeplink": "false",
        "draft_is_invisible": False,
        "draft_is_web_article_video": False,
        "draft_materials": [
            {"type": i, "value": []} for i in [0, 1, 2, 3, 6, 7, 8]
        ],
        "draft_materials_copied_info": [],
        "draft_name": Path(video_path).stem,
        "draft_need_rename_folder": False,
        "draft_new_version": "",
        "draft_removable_storage_device": "",
        "draft_root_path": str(Path(output_path).parent),
        "draft_segment_extra_info": [],
        "draft_timeline_materials_size_": 0,
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1,
        "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1,
        "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1,
        "tm_draft_create": current_time_ms,
        "tm_draft_modified": current_time_ms,
        "tm_draft_removed": 0,
        "tm_duration": 0
    }

    # Salva i file JSON
    with open(os.path.join(output_path, 'draft_info.json'), 'w', encoding='utf-8') as f:
        json.dump(draft_info, f, indent=0, ensure_ascii=False)

    with open(os.path.join(output_path, 'draft_meta_info.json'), 'w', encoding='utf-8') as f:
        json.dump(draft_meta_info, f, indent=0, ensure_ascii=False)

    # Altri file necessari
    with open(os.path.join(output_path, 'draft_settings'), 'w') as f:
        f.write('{"draft_auto_save_status":true,"draft_save_status":true,"draft_use_audio_denoise_status":false,"multi_lang_reco_id":""}')

    with open(os.path.join(output_path, 'performance_opt_info.json'), 'w') as f:
        f.write('{"performance_opt":false,"performance_opt_biz_line":0}')

    with open(os.path.join(output_path, 'attachment_editing.json'), 'w') as f:
        f.write('{"audition_list":[],"audition_status":-1,"edit_status":0,"need_manual_open":false}')

    with open(os.path.join(output_path, 'attachment_pc_common.json'), 'w') as f:
        f.write('{"attachment_biz_data":"","cloud_folder":{},"cloud_media":[],"import_to_media":false}')

    with open(os.path.join(output_path, 'draft_agency_config.json'), 'w') as f:
        f.write('{"agency_config":[],"agency_extra":"","client_info":{"activity_id":"","agency_id":"","brand_name":""},"export_time":0}')

    with open(os.path.join(output_path, 'draft_biz_config.json'), 'w') as f:
        f.write('')

    # Crea file .locked (indica che il progetto è in uso da CapCut)
    with open(os.path.join(output_path, '.locked'), 'w') as f:
        f.write('')

    # Crea sottocartelle necessarie
    for folder in ['Resources', 'adjust_mask', 'common_attachment', 'matting', 'qr_upload', 'smart_crop', 'subdraft']:
        os.makedirs(os.path.join(output_path, folder), exist_ok=True)

    original_duration = float(video_info['format']['duration'])
    trimmed_duration = sum(end - start for start, end in kept_segments)
    saved_time = original_duration - trimmed_duration

    print(f"✓ Progetto CapCut creato in: {output_path}")
    print(f"  Durata originale: {original_duration:.2f}s")
    print(f"  Segmenti tagliati: {len(kept_segments)}")
    print(f"  Tempo risparmiato: {saved_time:.2f}s ({saved_time/original_duration*100:.1f}%)")

    # Controlla se è nella directory di CapCut
    capcut_dir = str(Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft")
    if output_path.startswith(capcut_dir):
        print(f"\n✨ Il progetto apparirà automaticamente in CapCut Desktop!")
        print(f"   Apri CapCut e troverai il progetto '{Path(output_path).name}' nella lista")
    else:
        print(f"\nNOTA: Importa questa cartella in CapCut Desktop:")
        print(f"  File → Open Project → Seleziona la cartella '{Path(output_path).name}'")


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
                       help='Modello Whisper per i sottotitoli (default: medium)')

    args = parser.parse_args()

    # Verifica dipendenze
    check_dependencies()

    # Verifica che il file video esista
    if not os.path.exists(args.input_video):
        raise FileNotFoundError(f"File video non trovato: {args.input_video}")

    # Determina il percorso di output usando il nome del file video
    video_name = Path(args.input_video).stem
    output_folder = video_name

    # Ottieni informazioni sul video
    video_info = get_video_info(args.input_video)
    video_duration = float(video_info['format']['duration'])
    video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
    fps = eval(video_stream.get('r_frame_rate', '30/1')) if video_stream else 30.0

    print(f"\n{'='*60}")
    print(f"Video Silence Cutter")
    print(f"{'='*60}")
    print(f"Video: {args.input_video}")
    print(f"Durata: {video_duration:.2f}s")
    print(f"Output: {output_folder}")
    print(f"Modello Whisper: {args.whisper_model}")
    print(f"{'='*60}\n")

    # Crea directory temporanea
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, 'audio.wav')
        srt_path = os.path.join(tmpdir, 'subtitles.srt')

        # Estrai audio con riduzione rumore (sempre attiva)
        extract_audio(args.input_video, audio_path, noise_reduction=True)

        # Analizza silenzi
        silence_intervals = analyze_audio_silence(
            audio_path,
            args.threshold,
            args.duration
        )

        # Genera sottotitoli
        subtitle_segments = generate_subtitles_whisper(args.input_video, srt_path, model_size=args.whisper_model)

        # Unisci intervalli di silenzio
        merged_silence = merge_silence_intervals(
            silence_intervals,
            subtitle_segments,
            args.merge
        )

        print(f"\nIntervalli di silenzio da rimuovere: {len(merged_silence)}")
        for i, (start, end) in enumerate(merged_silence[:10], 1):
            print(f"  {i}. {start:.2f}s - {end:.2f}s (durata: {end-start:.2f}s)")
        if len(merged_silence) > 10:
            print(f"  ... e altri {len(merged_silence) - 10}")

        # Determina nome base per i file
        name_no_ext = Path(args.input_video).stem + "_tagliato"

        # Crea cartella di output
        os.makedirs(output_folder, exist_ok=True)

        # Usa process_and_export per generare tutto
        process_and_export(
            video_path=args.input_video,
            silence_cuts=merged_silence,
            ai_cuts=[],  # Nessun taglio AI dal CLI per ora
            video_duration=video_duration,
            output_folder=output_folder,
            video_info=video_info,
            name_no_ext=name_no_ext,
            subtitle_segments=subtitle_segments,
            save_subtitles=True
        )


if __name__ == '__main__':
    main()
