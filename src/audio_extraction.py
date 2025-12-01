#!/usr/bin/env python3
"""
Flusso 2: Estrazione e Separazione Audio
Estrae l'audio dal video con opzionale separazione vocale AI.
"""

import os
import subprocess
from typing import Optional


def extract_audio_standard(video_path: str, output_audio: str, noise_reduction: bool = False) -> None:
    """
    Estrae l'audio dal video usando metodo standard FFmpeg.

    :param video_path: Percorso del video
    :param output_audio: Percorso output audio WAV
    :param noise_reduction: Applica filtri di riduzione rumore
    """
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


def extract_audio_with_vocal_separation(video_path: str, output_audio: str) -> Optional[str]:
    """
    Estrae l'audio dal video con separazione vocale AI.

    :param video_path: Percorso del video
    :param output_audio: Percorso output audio WAV per analisi
    :return: Percorso del file vocals completo per il video finale (o None se fallito)
    """
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

            return vocals_full_path
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
            return None

    except ImportError:
        print("\naudio-separator non installato, uso estrazione standard")
        print("   Installa con: pip install audio-separator")
        return None
    except Exception as e:
        print(f"\nErrore durante separazione vocals: {e}")
        print("   Fallback a estrazione standard")
        return None


def extract_audio(video_path: str, output_audio: str,
                 noise_reduction: bool = True,
                 separate_vocals: bool = True) -> Optional[str]:
    """
    Estrae l'audio dal video con separazione vocale opzionale.

    :param video_path: Percorso del video
    :param output_audio: Percorso output audio WAV per analisi
    :param noise_reduction: Applica filtri di riduzione rumore FFmpeg (deprecato, usa separate_vocals)
    :param separate_vocals: Separa i vocals dal resto usando AI (consigliato)
    :return: Percorso del file vocals completo per il video finale (o None se non separato)
    """
    if separate_vocals:
        vocals_path = extract_audio_with_vocal_separation(video_path, output_audio)
        if vocals_path:
            return vocals_path
        # Se fallisce, continua con metodo standard

    # Fallback o metodo standard senza separazione vocals
    extract_audio_standard(video_path, output_audio, noise_reduction)
    return None


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Uso: python 2_audio_extraction.py <video_path> <output_audio>")
        sys.exit(1)

    video = sys.argv[1]
    output = sys.argv[2]
    vocals = extract_audio(video, output, separate_vocals=True)
    print(f"Audio estratto: {output}")
    if vocals:
        print(f"Vocals estratti: {vocals}")
