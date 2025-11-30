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
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import numpy as np
from datetime import datetime
import uuid

# Tenta di importare dotenv per caricare il file .env
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


# Logger per le fasi
def log_phase(phase_name):
    """Stampa il nome della fase corrente"""
    print(f"\n[{phase_name}]")


def check_dependencies():
    """Verifica che ffmpeg sia installato."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("ffmpeg non è installato. Installalo con: brew install ffmpeg (macOS) o apt-get install ffmpeg (Linux)")


def extract_audio(video_path: str, output_audio: str, noise_reduction: bool = True, separate_vocals: bool = True) -> str:
    """
    Estrae l'audio dal video con separazione vocale opzionale.

    :param video_path: Percorso del video
    :param output_audio: Percorso output audio WAV per analisi
    :param noise_reduction: Applica filtri di riduzione rumore FFmpeg (deprecato, usa separate_vocals)
    :param separate_vocals: Separa i vocals dal resto usando AI (consigliato)
    :return: Percorso del file vocals completo per il video finale (o None se non separato)
    """
    vocals_full_path = None

    if separate_vocals:
        try:
            from audio_separator.separator import Separator
            import sys
            import io

            print("Estraendo audio dal video...", end='', flush=True)
            # Prima estrai l'audio grezzo in un file temporaneo
            temp_audio = output_audio.replace('.wav', '_temp.wav')
            subprocess.run([
                'ffmpeg', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le',
                '-ar', '44100',  # Usa sample rate più alto per audio-separator
                '-ac', '2',       # Stereo per migliore separazione
                '-y',
                temp_audio
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(" ")

            print("Separando voce dal rumore di fondo con AI...", end='', flush=True)

            # Nascondi i log di audio-separator
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            try:
                # Inizializza audio-separator
                separator = Separator()

                # Carica il modello MDX-Net (veloce e preciso)
                separator.load_model(model_filename='UVR-MDX-NET-Inst_HQ_3.onnx')

                # Separa l'audio (crea due file: Vocals e Instrumental)
                output_files = separator.separate(temp_audio)
            finally:
                # Ripristina stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            print(" ")

            # Trova il file Vocals
            vocals_file = None
            for file in output_files:
                if 'Vocals' in file or 'vocals' in file:
                    vocals_file = file
                    break

            if vocals_file and os.path.exists(vocals_file):
                # Salva il file vocals completo per il video finale (alta qualità)
                vocals_full_path = output_audio.replace('.wav', '_vocals_full.wav')
                subprocess.run([
                    'ffmpeg', '-i', vocals_file,
                    '-acodec', 'pcm_s16le',
                    '-ar', '44100',  # Alta qualità per video finale
                    '-ac', '2',       # Stereo
                    '-y',
                    vocals_full_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                # Converti il file vocals al formato per analisi (16kHz mono)
                print("Ottimizzando voce per analisi...", end='', flush=True)
                subprocess.run([
                    'ffmpeg', '-i', vocals_file,
                    '-acodec', 'pcm_s16le',
                    '-ar', '16000',  # Sample rate per analisi silenzi
                    '-ac', '1',       # Mono
                    '-y',
                    output_audio
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                print(" ")

                # Pulisci file temporanei
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)
                if os.path.exists(vocals_file):
                    os.remove(vocals_file)
                # Rimuovi anche il file instrumental se esiste
                instrumental_file = vocals_file.replace('Vocals', 'Instrumental').replace('vocals', 'instrumental')
                if os.path.exists(instrumental_file):
                    os.remove(instrumental_file)
            else:
                print(" Fallback a estrazione standard")
                # Fallback: usa il file temporaneo convertito
                subprocess.run([
                    'ffmpeg', '-i', temp_audio,
                    '-acodec', 'pcm_s16le',
                    '-ar', '16000',
                    '-ac', '1',
                    '-y',
                    output_audio
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)

        except ImportError:
            print("\naudio-separator non installato, uso estrazione standard")
            print("   Installa con: pip install audio-separator")
            # Fallback a estrazione standard
            separate_vocals = False
        except Exception as e:
            print(f"\nErrore durante separazione vocals: {e}")
            print("   Fallback a estrazione standard")
            separate_vocals = False

    # Fallback o metodo standard senza separazione vocals
    if not separate_vocals:
        if noise_reduction:
            print("Estraendo e ripulendo audio...", end='', flush=True)
            # Filtro audio complesso per ridurre il rumore di fondo
            audio_filter = (
                "highpass=f=200,"           # Rimuove rumori bassi (< 200Hz)
                "lowpass=f=3000,"            # Rimuove rumori alti (> 3000Hz) - mantiene voce umana
                "afftdn=nf=-25,"             # FFT denoiser - riduce rumore
                "anlmdn=s=0.00001:p=0.002:r=0.002,"  # Non-local means denoiser
                "loudnorm"                   # Normalizza il volume
            )
        else:
            print("Estraendo audio...", end='', flush=True)
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
        print(" ")

    return vocals_full_path


def analyze_audio_silence(audio_path: str, silence_threshold_db: float = -40,
                         min_silence_duration: float = 0.5) -> List[Tuple[float, float]]:
    """Analizza l'audio e trova gli intervalli di silenzio usando ffmpeg."""
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


def generate_subtitles_whisper(video_path: str, output_srt: str = None, words_per_segment: int = 3, model_size: str = "medium") -> List[Dict]:
    """
    Genera sottotitoli usando Whisper con segmenti di N parole.

    :param video_path: Percorso del video
    :param output_srt: Percorso output SRT (opzionale, per file temporaneo)
    :param words_per_segment: Numero di parole per segmento per l'analisi silenzi (default: 3)
    :param model_size: Dimensione del modello Whisper (tiny, base, small, medium, large, default: medium)
    :return: Lista di segmenti sottotitoli
    """
    try:
        import whisper
        print(f"Generando trascrizione con Whisper {model_size} (segmenti di ~{words_per_segment} parole)...")

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

        # Salva file SRT temporaneo solo se richiesto
        if output_srt:
            with open(output_srt, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    f.write(f"{i}\n")
                    f.write(f"{format_timestamp_srt(segment['start'])} --> {format_timestamp_srt(segment['end'])}\n")
                    f.write(f"{segment['text']}\n\n")

        return segments
    except ImportError:
        print("ATTENZIONE: openai-whisper non è installato. Installalo con: pip install openai-whisper")
        return []


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


def process_and_export(video_path: str, silence_cuts: List[Tuple[float, float]],
                      ai_cuts: List[Tuple[float, float]], video_duration: float,
                      output_folder: str, video_info: Dict = None, name_no_ext: str = None,
                      subtitle_segments: List[Dict] = None, save_subtitles: bool = True,
                      vocals_audio_path: str = None) -> None:
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
    keep_ranges = []
    current_pos = 0.0
    for cs, ce in merged_cuts:
        if cs > current_pos and (cs - current_pos) > 0.1:
            keep_ranges.append((current_pos, cs))
        current_pos = max(current_pos, ce)

    if current_pos < video_duration:
        keep_ranges.append((current_pos, video_duration))

    # Calcola statistiche
    original_duration = video_duration
    trimmed_duration = sum(end - start for start, end in keep_ranges)
    saved_time = original_duration - trimmed_duration

    print(f"Segmenti: {len(keep_ranges)} | Risparmio: {saved_time:.1f}s ({saved_time/original_duration*100:.1f}%)")

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
    edl_path = os.path.join(output_folder, "premiere_pro.edl")
    generate_edl(keep_ranges, video_path, edl_path, video_info)

    # 5. Genera Segmenti
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

    print("Segmenti video salvati in:", chunks_dir)

    # 7. Salva sottotitoli se disponibili
    if save_subtitles and subtitle_segments:
        # Ri-segmenta i sottotitoli a 8 parole per l'esportazione
        export_segments = resegment_subtitles(subtitle_segments, words_per_segment=8)

        # Salva in formato SRT
        srt_path = os.path.join(output_folder, "subtitles.srt")
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(export_segments, 1):
                f.write(f"{i}\n")
                f.write(f"{format_timestamp_srt(segment['start'])} --> {format_timestamp_srt(segment['end'])}\n")
                f.write(f"{segment['text']}\n\n")

        # Salva in formato JSON
        json_path = os.path.join(output_folder, "subtitles.json")
        save_subtitles_json(export_segments, json_path, video_path)

        # Salva in formato TXT
        txt_path = os.path.join(output_folder, "transcript.txt")
        save_subtitles_txt(export_segments, txt_path)

        # Genera metadati AI con Gemini (se disponibile)
        generate_video_metadata(txt_path, output_folder)

    # 8. Sposta il video originale nella cartella di output
    original_video_name = Path(video_path).name
    destination_path = os.path.join(output_folder, original_video_name)

    # Verifica se il video originale non è già nella cartella di output
    if os.path.abspath(video_path) != os.path.abspath(destination_path):
        shutil.move(video_path, destination_path)


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



def analyze_with_gemini(transcript: str, api_key: str) -> Dict[str, str]:
    """
    Analizza la trascrizione usando Google Gemini API.
    """
    try:
        import google.generativeai as genai

        # Configura Gemini
        genai.configure(api_key=api_key)

        model_name = 'gemini-3-pro-preview'
        model = genai.GenerativeModel(model_name)

        # Prompt per l'analisi
        prompt = f"""Analizza la seguente trascrizione di un video e genera:

1. **TITOLO**: Un titolo accattivante e SEO-friendly per il video (max 70 caratteri)
2. **DESCRIZIONE**: Una descrizione dettagliata del contenuto del video (200-300 parole) scritta in prima persona
3. **TAGS**: Una lista di 10-15 tag rilevanti per il video, separati da virgola. I tag devono essere specifici, SEO-friendly e rappresentare i concetti chiave trattati nel video.
4. **PROMPT_IMMAGINE**: Un prompt dettagliato in inglese per generare un'immagine di copertina usando un modello AI text-to-image. Il prompt deve descrivere l'argomento/tema trattato nel video (non il contesto di realizzazione), essere descrittivo, specifico e adatto a Stable Diffusion / DALL-E.

Formato della risposta (JSON):
{{
  "titolo": "...",
  "descrizione": "...",
  "tags": "tag1, tag2, tag3, ...",
  "prompt_immagine": "..."
}}

TRASCRIZIONE:
{transcript}

Rispondi SOLO con il JSON, senza altro testo."""


        # Genera risposta
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Pulisci il JSON dalla risposta
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()

        # Parse JSON
        try:
            metadata = json.loads(response_text)
            return metadata
        except json.JSONDecodeError:
            print("Errore nel parsing JSON. Testo ricevuto:")
            print(response_text)
            # Fallback
            return {
                "titolo": "Video senza titolo",
                "descrizione": transcript[:300] + "..." if len(transcript) > 300 else transcript,
                "tags": "",
                "prompt_immagine": "professional video thumbnail, high quality"
            }

    except ImportError:
        print("google-generativeai non installato. Salta generazione metadati.")
        return None
    except Exception as e:
        error_message = str(e)
        if "quota" in error_message.lower() or "rate limit" in error_message.lower():
            print(f"Errore di quota API superata!")
            print(f"   Stai usando {model_name}. Attendi qualche minuto o passa a gemini-1.5-flash.")
        else:
            print(f"Errore durante l'analisi con Gemini: {e}")
        return None


def generate_thumbnail_with_gemini(image_prompt: str, api_key: str, output_path: str, personal_image_path: str = "personal_image.png") -> bool:
    """
    Genera un'immagine di copertina YouTube usando Gemini 3 Pro con generazione immagini.

    :param image_prompt: Prompt per la generazione dell'immagine
    :param api_key: Chiave API di Google Gemini
    :param output_path: Percorso dove salvare l'immagine generata
    :param personal_image_path: Percorso dell'immagine personale da includere
    :return: True se generata con successo, False altrimenti
    """
    try:
        from google import genai
        from google.genai import types
        from PIL import Image
        import io


        # Verifica immagine personale
        if os.path.exists(personal_image_path):
            with open(personal_image_path, 'rb') as f:
                personal_image_bytes = f.read()
            personal_image_part = types.Part.from_bytes(data=personal_image_bytes, mime_type='image/png')
        else:
            personal_image_part = None

        # Costruisci prompt dettagliato per thumbnail YouTube
        if personal_image_part:
            full_prompt = f"""Create a professional YouTube thumbnail with these specifications:

LAYOUT: 16:9 aspect ratio (1920x1080), split composition with person on one side and content on the other

PERSON STYLING: Integrate the person from the provided image seamlessly into the scene. The person should appear natural and engaging, with proper lighting that matches the overall aesthetic. Position them prominently but balanced with the content side.

CONTENT SIDE: {image_prompt}

OVERALL STYLE: Professional YouTube thumbnail quality, vibrant colors, high contrast, dramatic lighting, balanced composition, eye-catching yet cohesive design"""
        else:
            full_prompt = f"""Create a professional YouTube thumbnail with these specifications:

LAYOUT: 16:9 aspect ratio (1920x1080)

CONTENT: {image_prompt}

OVERALL STYLE: Professional YouTube thumbnail quality, vibrant colors, high contrast, dramatic lighting, balanced composition, eye-catching design"""


        # Salva il prompt completo in un file TXT
        prompt_file_path = output_path.replace('thumbnail.png', 'prompt.txt')
        try:
            with open(prompt_file_path, 'w', encoding='utf-8') as f:
                f.write(full_prompt)
            print(f"File prompt thumbnail generato!")
        except Exception as e:
            print(f"Errore salvataggio prompt: {e}")

        # Client con timeout standard
        client = genai.Client(api_key=api_key)

        # Contenuto
        contents = [full_prompt]
        if personal_image_part:
            contents.append(personal_image_part)


        # Genera
        response = client.models.generate_content(
            model='models/gemini-3-pro-image-preview',
            contents=contents,
            config=types.GenerateContentConfig(
                image_config=types.ImageConfig(
                    aspect_ratio='16:9',
                    image_size='4K'
                )
            )
        )

        # Estrai immagine
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]

            for part in candidate.content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    image_data = part.inline_data.data
                    pil_image = Image.open(io.BytesIO(image_data))

                    # Ridimensiona
                    if pil_image.size != (1920, 1080):
                        pil_image = pil_image.resize((1920, 1080), Image.Resampling.LANCZOS)

                    # Salva
                    pil_image.save(output_path, 'PNG', quality=95)
                    print(f"File thumbnail generato!")
                    return True

            return False
        else:
            return False

    except Exception as e:
        print(f"Errore: {e}")
        print(f"   Tipo: {type(e).__name__}")
        return False


def save_metadata(metadata: Dict[str, str], output_path: str) -> None:
    """
    Salva i metadati in un file TXT.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("METADATI VIDEO\n")
            f.write("=" * 80 + "\n\n")

            f.write("TITOLO\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('titolo', 'N/A') + "\n\n")

            f.write("DESCRIZIONE\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('descrizione', 'N/A') + "\n\n")

            f.write("TAGS\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('tags', 'N/A') + "\n\n")

            f.write("PROMPT IMMAGINE\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('prompt_immagine', 'N/A') + "\n\n")

        print(f"File metadati generato!")

    except Exception as e:
        print(f"Errore durante il salvataggio metadati: {e}")


def generate_video_metadata(transcript_path: str, output_folder: str, api_key: Optional[str] = None) -> None:
    """
    Genera metadati video analizzando la trascrizione con Google Gemini.

    :param transcript_path: Percorso del file di trascrizione
    :param output_folder: Cartella dove salvare i metadati
    :param api_key: Chiave API Gemini (opzionale, usa .env se non specificata)
    """
    # Carica API key da .env se non specificata
    if not api_key:
        api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("Chiave API Gemini non trovata. Salta generazione metadati.")
        print("   Aggiungi GEMINI_API_KEY al file .env per abilitare questa funzionalità.")
        return

    # Carica trascrizione
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = f.read().strip()
    except Exception as e:
        print(f"Errore lettura trascrizione: {e}")
        return

    log_phase("Generazione metadati AI con Gemini")

    # Analizza con Gemini
    metadata = analyze_with_gemini(transcript, api_key)

    if not metadata:
        return

    # Salva metadati
    metadata_path = os.path.join(output_folder, "metadata.txt")
    save_metadata(metadata, metadata_path)

    # Genera thumbnail YouTube con Gemini (se disponibile)
    if metadata.get('prompt_immagine'):
        # Determina percorso dell'immagine personale (nella root del progetto)
        project_root = Path(__file__).parent
        personal_image_path = str(project_root / "personal_image.png")

        # Determina percorso output thumbnail
        thumbnail_path = os.path.join(output_folder, "thumbnail.png")

        generate_thumbnail_with_gemini(
            image_prompt=metadata['prompt_immagine'],
            api_key=api_key,
            output_path=thumbnail_path,
            personal_image_path=personal_image_path
        )


def main():
    # --- CARICAMENTO .ENV ---
    if DOTENV_AVAILABLE:
        load_dotenv()
    # ------------------------
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
    parser.add_argument('--words-per-segment', type=int, default=3,
                       help='Numero di parole per segmento per analisi silenzi (default: 3)')
    parser.add_argument('--no-whisper', action='store_true',
                       help='Salta la generazione di sottotitoli e metadati AI con Whisper/Gemini')

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
        print(f"Words per segment: {args.words_per_segment}")
    else:
        print("Whisper: DISABLED")
    print("="*100)

    # Verifica dipendenze
    log_phase("Verifica dipendenze")
    check_dependencies()

    # Verifica che il file video esista
    if not os.path.exists(args.input_video):
        raise FileNotFoundError(f"File video non trovato: {args.input_video}")

    # Determina il percorso di output: output/{nome_video}/
    video_name = Path(args.input_video).stem
    output_folder = os.path.join("output", video_name)

    # Ottieni informazioni sul video
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
        srt_path = os.path.join(tmpdir, 'subtitles.srt')

        # Estrai audio con separazione vocale (mantieni vocals solo in tmpdir)
        log_phase("Estrazione audio")
        vocals_full_path = extract_audio(args.input_video, audio_path, noise_reduction=True, separate_vocals=True)

        # Analizza silenzi
        log_phase("Analisi silenzi")
        silence_intervals = analyze_audio_silence(
            audio_path,
            args.threshold,
            args.duration
        )

        # Genera sottotitoli (se non disabilitato)
        if args.no_whisper:
            subtitle_segments = []
        else:
            log_phase("Trascrizione Whisper")
            subtitle_segments = generate_subtitles_whisper(
                args.input_video,
                srt_path,
                words_per_segment=args.words_per_segment,
                model_size=args.whisper_model
            )

        # Unisci intervalli di silenzio
        log_phase("Unione intervalli silenzi")
        merged_silence = merge_silence_intervals(
            silence_intervals,
            subtitle_segments if not args.no_whisper else [],
            args.merge
        )
        print(f"Intervalli da rimuovere: {len(merged_silence)}")

        # Determina nome base per i file
        name_no_ext = Path(args.input_video).stem + "_tagliato"

        # Usa process_and_export per generare tutto
        log_phase("Export video e file")
        process_and_export(
            video_path=args.input_video,
            silence_cuts=merged_silence,
            ai_cuts=[],  # Nessun taglio AI dal CLI per ora
            video_duration=video_duration,
            output_folder=output_folder,
            video_info=video_info,
            name_no_ext=name_no_ext,
            subtitle_segments=subtitle_segments,
            save_subtitles=not args.no_whisper,
            vocals_audio_path=vocals_full_path
        )


if __name__ == '__main__':
    main()
