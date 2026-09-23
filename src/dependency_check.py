#!/usr/bin/env python3
"""
Flusso 1: Verifica Dipendenze
Controlla che tutte le dipendenze richieste siano installate.
"""

import subprocess
from typing import Dict


def check_ffmpeg() -> bool:
    """Verifica che ffmpeg sia installato."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_ffprobe() -> bool:
    """Verifica che ffprobe sia installato."""
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_whisper() -> bool:
    """Verifica che openai-whisper sia installato."""
    try:
        import whisper
        return True
    except ImportError:
        return False


def check_audio_separator() -> bool:
    """Verifica che audio-separator sia installato E funzionante.

    Oltre all'import controlla le dipendenze interne (audioread) perché il
    pacchetto può risultare installato ma rompersi all'import: in quel caso
    segnalarlo come assente evita l'errore fuorviante a runtime.
    """
    try:
        from audio_separator.separator import Separator  # noqa: F401
        return True
    except ImportError:
        return False


def check_deepgram() -> bool:
    """Verifica che deepgram-sdk sia installato."""
    try:
        from deepgram import DeepgramClient
        return True
    except ImportError:
        return False


def check_anthropic() -> bool:
    """Verifica che anthropic sia installato."""
    try:
        import anthropic
        return True
    except ImportError:
        return False


def check_openai() -> bool:
    """Verifica che openai sia installato."""
    try:
        import openai
        return True
    except ImportError:
        return False


def check_dotenv() -> bool:
    """Verifica che python-dotenv sia installato."""
    try:
        from dotenv import load_dotenv
        return True
    except ImportError:
        return False


def check_all_dependencies(verbose: bool = True) -> Dict[str, bool]:
    """
    Verifica tutte le dipendenze e ritorna un dizionario con lo stato.

    :param verbose: Se True, stampa i risultati
    :return: Dizionario {nome_dipendenza: bool}
    """
    dependencies = {
        'ffmpeg': check_ffmpeg(),
        'ffprobe': check_ffprobe(),
        'whisper': check_whisper(),
        'audio_separator': check_audio_separator(),
        'deepgram': check_deepgram(),
        'anthropic': check_anthropic(),
        'openai': check_openai(),
        'dotenv': check_dotenv()
    }

    if verbose:
        print("Verifica dipendenze:")
        print("-" * 40)
        for dep, status in dependencies.items():
            status_icon = "✓" if status else "✗"
            print(f"{status_icon} {dep}: {'OK' if status else 'NON TROVATO'}")
        print("-" * 40)

    return dependencies


def check_dependencies() -> None:
    """
    Verifica le dipendenze critiche e solleva un'eccezione se mancanti.
    """
    if not check_ffmpeg():
        raise RuntimeError(
            "ffmpeg non è installato. Installalo con:\n"
            "  macOS: brew install ffmpeg\n"
            "  Linux: apt-get install ffmpeg\n"
            "  Windows: scoop install ffmpeg"
        )

    if not check_ffprobe():
        raise RuntimeError(
            "ffprobe non è installato. Di solito viene fornito con ffmpeg.\n"
            "Reinstalla ffmpeg per ottenerlo."
        )


if __name__ == '__main__':
    check_all_dependencies(verbose=True)
