#!/usr/bin/env python3
"""
Shared utilities for AutoVideoMaker
"""

import json
from pathlib import Path
from typing import Dict


def log_phase(phase_name: str) -> None:
    """Stampa il nome della fase corrente"""
    print(f"\n[{phase_name}]")


def format_timestamp_srt(seconds: float) -> str:
    """Formatta i secondi in formato timestamp SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def get_video_info(video_path: str) -> Dict:
    """Ottiene informazioni sul video usando ffprobe."""
    import subprocess

    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_format', '-show_streams',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)
