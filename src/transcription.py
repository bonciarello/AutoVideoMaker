#!/usr/bin/env python3
"""
Flusso 4: Trascrizione Audio
Genera la trascrizione usando Deepgram (default) o Whisper AI.

Deepgram è il metodo di default: è veloce (API cloud) e non richiede
il download di modelli. Richiede DEEPGRAM_API_KEY nel file .env.
Se Deepgram non è configurato o fallisce, viene fatto fallback
automatico a Whisper (locale).

Ogni parola ha: id (posizione nella lista), start/end (secondi), word
(forma normalizzata), text (con punteggiatura, es. "a...") e confidence.
La trascrizione si salva in words.json e si riusa ai rilanci.
"""

import os
import json
from pathlib import Path
from typing import Optional

from utils import normalize_word

# Versione del formato di words.json
WORDS_FILE_VERSION = 1


def _with_ids(words: list) -> list:
    """Numera le parole in ordine: l'id è la posizione nella lista."""
    for i, w in enumerate(words):
        w['id'] = i
    return words


def deepgram_words(items) -> list:
    """
    Converte le parole della risposta Deepgram nel formato interno.

    :param items: Parole Deepgram (word, start, end e, se presenti,
           punctuated_word e confidence)
    :return: [{"id", "start", "end", "word", "text", "confidence"}, ...]
    """
    words = []
    for w in items or []:
        raw = getattr(w, 'word', None) or ''
        text = (getattr(w, 'punctuated_word', None) or raw).strip()
        if not text:
            continue
        words.append({
            'start': float(w.start),
            'end': float(w.end),
            'word': normalize_word(raw or text),
            'text': text,
            'confidence': float(getattr(w, 'confidence', None) or 0.0),
        })
    return _with_ids(words)


def whisper_words(segments) -> list:
    """
    Converte le parole dei segmenti Whisper nel formato interno
    (i token vuoti vengono scartati).
    """
    words = []
    for seg in segments or []:
        for w in seg.get('words', []):
            text = (w.get('word') or '').strip()
            if not text:
                continue
            words.append({
                'start': float(w['start']),
                'end': float(w['end']),
                'word': normalize_word(text),
                'text': text,
                'confidence': float(w.get('probability', 0.0)),
            })
    return _with_ids(words)


def transcribe_deepgram(audio_path: str,
                        language: str = "it",
                        model: str = "nova-3") -> dict:
    """
    Genera trascrizione usando Deepgram API, con timestamp a livello di parola.

    :param audio_path: Percorso del file audio (WAV)
    :param language: Lingua della trascrizione (default: it)
    :param model: Modello Deepgram (default: nova-3)
    :return: {"text": str, "words": [...]} (liste vuote se fallita)
    """
    # Carica .env per ottenere la chiave API
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv non disponibile, usa variabili d'ambiente del sistema

    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        print("DEEPGRAM_API_KEY non trovata nel file .env.")
        return {"text": "", "words": []}

    try:
        from deepgram import DeepgramClient
    except ImportError:
        print("deepgram-sdk non installato. Installalo con: pip install deepgram-sdk")
        return {"text": "", "words": []}

    try:
        print(f"Generando trascrizione con Deepgram ({model})...")
        client = DeepgramClient(api_key=api_key)

        with open(audio_path, 'rb') as audio_file:
            buffer_data = audio_file.read()

        # API deepgram-sdk >= 5.x
        response = client.listen.v1.media.transcribe_file(
            request=buffer_data,
            model=model,
            language=language,
            smart_format=True,
            punctuate=True
        )

        alternative = response.results.channels[0].alternatives[0]
        text = alternative.transcript.strip()

        # Parole con timestamp e punteggiatura (i «...» servono alla pulizia take)
        words = deepgram_words(alternative.words)

        print(f"   ({len(words)} parole rilevate)")
        return {"text": text, "words": words}

    except Exception as e:
        print(f"Errore durante la trascrizione Deepgram: {e}")
        return {"text": "", "words": []}


def transcribe_whisper(audio_path: str,
                       model_size: str = "medium",
                       language: str = "it") -> dict:
    """
    Genera trascrizione usando Whisper, con timestamp a livello di parola.

    :param audio_path: Percorso del file audio (WAV)
    :param model_size: Dimensione del modello Whisper (tiny, base, small, medium, large)
    :param language: Lingua della trascrizione (default: it)
    :return: {"text": str, "words": [...]} (liste vuote se fallita)
    """
    try:
        import whisper
    except ImportError:
        print("ATTENZIONE: openai-whisper non è installato. Installalo con: pip install openai-whisper")
        return {"text": "", "words": []}

    try:
        print(f"Generando trascrizione con Whisper {model_size}...")
        model = whisper.load_model(model_size)
        result = model.transcribe(audio_path, language=language, word_timestamps=True)

        text = result['text'].strip()
        words = whisper_words(result.get('segments', []))

        print(f"   ({len(words)} parole rilevate)")
        return {"text": text, "words": words}
    except Exception as e:
        print(f"Errore durante la trascrizione Whisper: {e}")
        return {"text": "", "words": []}


def transcribe_audio(audio_path: str,
                     transcriber: str = "deepgram",
                     whisper_model: str = "medium",
                     deepgram_model: str = "nova-3",
                     language: str = "it") -> dict:
    """
    Genera la trascrizione dell'audio con il servizio richiesto.

    Deepgram è il metodo di default. Se Deepgram non è configurato o
    fallisce, viene fatto fallback automatico a Whisper.

    :return: {"text", "words", "transcriber", "model"}: transcriber e model
             sono quelli effettivamente usati (dopo un eventuale fallback)
    """
    if transcriber == "deepgram":
        result = transcribe_deepgram(audio_path, language=language, model=deepgram_model)
        if result["text"]:
            return {**result, "transcriber": "deepgram", "model": deepgram_model}
        print("   Fallback a Whisper...")

    result = transcribe_whisper(audio_path, model_size=whisper_model, language=language)
    return {**result, "transcriber": "whisper", "model": whisper_model}


def save_words_json(path: str, transcription: dict, video_path: str,
                    video_duration: float, language: str) -> None:
    """
    Salva testo e parole in words.json, con i dati per riconoscere il video
    (nome, dimensione, durata) e le opzioni usate.
    """
    data = {
        'version': WORDS_FILE_VERSION,
        'video': {
            'name': Path(video_path).name,
            'size': os.path.getsize(video_path),
            'duration': round(video_duration, 3),
        },
        'transcriber': transcription.get('transcriber'),
        'model': transcription.get('model'),
        'language': language,
        'text': transcription.get('text', ''),
        'words': transcription.get('words', []),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def load_words_json(path: str, video_path: str, video_duration: float,
                    transcriber: str, language: str) -> Optional[dict]:
    """
    Riusa words.json se appartiene a questo video (nome, dimensione, durata
    entro 0,1 s) ed è stato fatto con lo stesso servizio e la stessa lingua.

    :return: {"text", "words", "transcriber", "model"} oppure None (file
             mancante, illeggibile o di un altro video/opzioni)
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        video = data['video']
        matches = (
            data.get('version') == WORDS_FILE_VERSION
            and video['name'] == Path(video_path).name
            and video['size'] == os.path.getsize(video_path)
            and abs(float(video['duration']) - video_duration) <= 0.1
            and data['language'] == language
            and data['transcriber'] == transcriber
        )
        if not matches:
            return None
        return {'text': data.get('text', ''), 'words': data['words'],
                'transcriber': data['transcriber'], 'model': data.get('model')}
    except (OSError, ValueError, KeyError, TypeError):
        return None


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python transcription.py <audio_path> [deepgram|whisper]")
        sys.exit(1)

    audio = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else "deepgram"
    result = transcribe_audio(audio, transcriber=method)
    text = result["text"]
    print(f"\nTrascrizione ({len(text)} caratteri, {len(result['words'])} parole):")
    print(text[:500] + ("..." if len(text) > 500 else ""))
