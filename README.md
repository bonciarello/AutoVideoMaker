# Video Silence Cutter

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg)
![OpenAI Whisper](https://img.shields.io/badge/Whisper-AI-orange.svg)
![Google Gemini](https://img.shields.io/badge/Gemini-AI-purple.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-AI-red.svg)

Tool automatico per tagliare i silenzi dai video e generare metadati AI con Google Gemini.

## Setup

### 1. Installa dipendenze di sistema

```bash
# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Windows
# Scarica ffmpeg da https://ffmpeg.org/download.html
```

### 2. Crea ambiente virtuale e installa dipendenze Python

```bash
python3 -m venv venv
source venv/bin/activate  # Su Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configura API Gemini (opzionale)

Se vuoi generare metadati AI e thumbnail, crea un file `.env` nella root:

```bash
GEMINI_API_KEY=your_api_key_here
```

Puoi ottenere una chiave API gratuita da [Google AI Studio](https://aistudio.google.com/app/apikey).

## Utilizzo

### Comando base

```bash
python3 video_silence_cutter.py tuo_video.mp4
```

### Opzioni disponibili

```bash
python3 video_silence_cutter.py tuo_video.mp4 \
  -t -40 \              # Soglia silenzio in dB (default: -40)
  -d 0.5 \              # Durata minima silenzio in secondi (default: 0.5)
  -m 1.0 \              # Distanza max per unire silenzi (default: 1.0)
  --whisper-model medium  # Modello Whisper: tiny, base, small, medium, large
```

### Disabilitare Whisper e metadati AI

```bash
python3 video_silence_cutter.py tuo_video.mp4 --no-whisper
```

## Output

Il tool genera una cartella `output/{nome_video}/` contenente:

- `chunks/` - Segmenti video tagliati
- `premiere_pro.edl` - File EDL per editing in Premiere Pro
- `transcript.txt` - Trascrizione completa del video (se Whisper abilitato)
- `metadata.txt` - Titolo, descrizione, tags generati da AI (se Gemini configurato)
- `thumbnail.png` - Miniatura YouTube generata da AI (se Gemini configurato)
- `prompt.txt` - Prompt usato per generare la thumbnail
- `{nome_video}.mp4` - Video originale spostato nella cartella

## Come funziona

1. **Estrazione audio** - Estrae e pulisce l'audio dal video
2. **Analisi silenzi** - Rileva gli intervalli di silenzio usando ffmpeg
3. **Trascrizione** - Genera trascrizione completa con Whisper AI (opzionale)
4. **Taglio video** - Crea segmenti video rimuovendo i silenzi
5. **Metadati AI** - Genera titolo, descrizione, tags e thumbnail con Gemini (opzionale)

## Requisiti

- Python 3.8+
- FFmpeg
- ~5 GB di spazio libero per i modelli AI (scaricati automaticamente al primo uso)

## Troubleshooting

### FFmpeg non trovato
Assicurati che ffmpeg sia installato e nel PATH:
```bash
ffmpeg -version
```

### Errore import Whisper
```bash
pip install openai-whisper
```

### Errore API Gemini
Verifica che `GEMINI_API_KEY` sia corretto nel file `.env`
