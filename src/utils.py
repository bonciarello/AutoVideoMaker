#!/usr/bin/env python3
"""
Shared utilities for AutoVideoMaker
"""

import json
import re
import subprocess
import unicodedata
from fractions import Fraction
from typing import Dict, Optional

# Modello Claude usato per metadati e pulizia take
CLAUDE_MODEL = 'claude-opus-5'

# Punteggiatura e simboli ai bordi di una parola
_EDGE_PUNCT_RE = re.compile(r"^[\W_]+|[\W_]+$")


def log_phase(phase_name: str) -> None:
    """Stampa il nome della fase corrente"""
    print(f"\n[{phase_name}]")


def parse_fps(video_stream: Optional[Dict], default: float = 30.0) -> float:
    """
    Estrae il frame rate da uno stream video ffprobe in modo sicuro (senza eval).

    :param video_stream: Dizionario dello stream video da ffprobe
    :param default: Valore di fallback se il frame rate non è disponibile
    :return: Frame rate come float
    """
    if not video_stream:
        return default

    rate = video_stream.get('avg_frame_rate') or video_stream.get('r_frame_rate')
    if not rate:
        return default

    try:
        fps = float(Fraction(rate))
    except (ValueError, ZeroDivisionError):
        return default

    return fps if fps > 0 else default


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


def normalize_word(text: str) -> str:
    """
    Forma normalizzata di una parola per i confronti: minuscolo, senza
    punteggiatura ai bordi. Gli apostrofi interni restano ("dall'alto").

    :param text: Parola così come trascritta (es. "Non", "è...", "«ciao»")
    :return: Parola normalizzata (es. "non", "è", "ciao"); stringa vuota se
             la parola è solo punteggiatura
    """
    t = unicodedata.normalize('NFC', text or '').lower().replace('’', "'")
    return _EDGE_PUNCT_RE.sub('', t)
