#!/usr/bin/env python3
"""
Flusso 4: Trascrizione Audio
Genera la trascrizione usando Deepgram (default) o Whisper AI.

Deepgram è il metodo di default: è veloce (API cloud) e non richiede
il download di modelli. Richiede DEEPGRAM_API_KEY nel file .env.
Se Deepgram non è configurato o fallisce, viene fatto fallback
automatico a Whisper (locale).
"""

import os


def transcribe_deepgram(audio_path: str,
                        language: str = "it",
                        model: str = "nova-3") -> dict:
    """
    Genera trascrizione usando Deepgram API, con timestamp a livello di parola.

    :param audio_path: Percorso del file audio (WAV)
    :param language: Lingua della trascrizione (default: it)
    :param model: Modello Deepgram (default: nova-3)
    :return: {"text": str, "words": [{"start", "end", "word"}, ...]}
             (liste vuote se fallita)
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

        # Estrai i timestamp a livello di parola (per tagli precisi sul parlato)
        words = []
        if alternative.words:
            for w in alternative.words:
                words.append({
                    'start': float(w.start),
                    'end': float(w.end),
                    'word': w.word
                })

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
    :return: {"text": str, "words": [{"start", "end", "word"}, ...]}
             (liste vuote se fallita)
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

        # Estrai i timestamp a livello di parola (per tagli precisi sul parlato)
        words = []
        for seg in result.get('segments', []):
            for w in seg.get('words', []):
                words.append({
                    'start': float(w['start']),
                    'end': float(w['end']),
                    'word': w['word'].strip()
                })

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

    :param audio_path: Percorso del file audio (WAV)
    :param transcriber: Servizio da usare: "deepgram" (default) o "whisper"
    :param whisper_model: Modello Whisper (usato solo con whisper o come fallback)
    :param deepgram_model: Modello Deepgram (default: nova-3)
    :param language: Lingua della trascrizione (default: it)
    :return: {"text": str, "words": [{"start", "end", "word"}, ...]}
    """
    if transcriber == "deepgram":
        result = transcribe_deepgram(audio_path, language=language, model=deepgram_model)
        if result["text"]:
            return result
        print("   Fallback a Whisper...")
        return transcribe_whisper(audio_path, model_size=whisper_model, language=language)

    return transcribe_whisper(audio_path, model_size=whisper_model, language=language)


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
