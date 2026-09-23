#!/usr/bin/env python3
"""
Shared utilities for AutoVideoMaker
"""

import json
import subprocess
from fractions import Fraction
from typing import Dict, Optional


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
