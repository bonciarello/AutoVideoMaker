# Video Silence Cutter - Architettura Modulare

## 📋 Panoramica

Il progetto è stato ristrutturato in moduli separati per migliorare la manutenibilità e la comprensione del codice. Ogni modulo rappresenta un flusso specifico dell'elaborazione video.

## 🗂️ Struttura dei Moduli

### File Principale
- **`video_silence_cutter.py`** - Orchestratore principale che coordina tutti i flussi

### Moduli di Flusso

#### 1️⃣ `flow_1_dependency_check.py`
**Scopo:** Verifica delle dipendenze del sistema

**Funzioni principali:**
- `check_ffmpeg()` - Verifica installazione FFmpeg
- `check_ffprobe()` - Verifica installazione FFprobe
- `check_whisper()` - Verifica installazione OpenAI Whisper
- `check_audio_separator()` - Verifica installazione audio-separator
- `check_gemini()` - Verifica installazione Google Gemini AI
- `check_dependencies()` - Verifica critica delle dipendenze essenziali

**Uso standalone:**
```bash
python flow_1_dependency_check.py
```

---

#### 2️⃣ `flow_2_audio_extraction.py`
**Scopo:** Estrazione e separazione audio dal video

**Funzioni principali:**
- `extract_audio_standard()` - Estrazione standard con FFmpeg
- `extract_audio_with_vocal_separation()` - Separazione vocale AI con audio-separator
- `extract_audio()` - Funzione wrapper principale

**Caratteristiche:**
- Separazione vocale AI (modello MDX-Net)
- Doppio output: alta qualità (44.1kHz stereo) + analisi (16kHz mono)
- Fallback automatico a estrazione standard
- Riduzione rumore opzionale con filtri FFmpeg

**Uso standalone:**
```bash
python flow_2_audio_extraction.py video.mp4 output_audio.wav
```

---

#### 3️⃣ `flow_3_silence_analysis.py`
**Scopo:** Analisi e rilevamento silenzi nell'audio

**Funzioni principali:**
- `analyze_audio_silence()` - Rileva intervalli di silenzio con FFmpeg
- `merge_silence_intervals()` - Unisce intervalli vicini e pause tra sottotitoli
- `calculate_kept_segments()` - Calcola segmenti da mantenere (inverso dei silenzi)

**Parametri configurabili:**
- Soglia dB (default: -40dB)
- Durata minima silenzio (default: 0.5s)
- Distanza merging (default: 1.0s)

**Uso standalone:**
```bash
python flow_3_silence_analysis.py audio.wav
```

---

#### 4️⃣ `flow_4_transcription.py`
**Scopo:** Trascrizione video con Whisper AI

**Funzioni principali:**
- `generate_subtitles_whisper()` - Trascrizione con segmentazione intelligente
- `resegment_subtitles()` - Ri-segmentazione per export
- `save_subtitles_srt()` - Export formato SRT
- `save_subtitles_json()` - Export formato JSON con metadata
- `save_subtitles_txt()` - Export solo testo

**Caratteristiche:**
- Word-level timestamps per precisione massima
- Segmentazione flessibile (default: 3 parole per analisi, 8 per export)
- Supporto modelli: tiny, base, small, medium, large
- Fallback automatico se word_timestamps non disponibile

**Uso standalone:**
```bash
python flow_4_transcription.py video.mp4 output.srt
```

---

#### 5️⃣ `flow_5_video_processing.py`
**Scopo:** Elaborazione video e generazione output

**Funzioni principali:**
- `generate_edl()` - Genera Edit Decision List per Premiere Pro
- `cut_video_segments()` - Taglia video in chunks con FFmpeg
- `calculate_statistics()` - Calcola statistiche sui tagli
- `process_and_export()` - Orchestratore completo export
- `move_original_video()` - Sposta video originale in output

**Output generati:**
- Chunks video (formato MP4, codec copy)
- File EDL per Premiere Pro
- Sottotitoli (SRT, JSON, TXT)
- Statistiche di risparmio tempo

**Uso standalone:**
```bash
python flow_5_video_processing.py video.mp4 cuts.json output/
```

---

#### 6️⃣ `flow_6_metadata_generation.py`
**Scopo:** Generazione metadati AI con Google Gemini

**Funzioni principali:**
- `analyze_with_gemini()` - Analisi trascrizione con Gemini
- `generate_thumbnail_with_gemini()` - Generazione thumbnail YouTube
- `save_metadata()` - Salvataggio metadati in TXT
- `generate_video_metadata()` - Orchestratore completo

**Output generati:**
- Titolo SEO-friendly (max 70 caratteri)
- Descrizione dettagliata (200-300 parole)
- 10-15 tag rilevanti
- Prompt per generazione immagine
- Thumbnail YouTube 1920x1080 (opzionale)

**Requisiti:**
- `GEMINI_API_KEY` in file `.env`
- (Opzionale) `personal_image.png` per thumbnail personalizzato

**Uso standalone:**
```bash
python flow_6_metadata_generation.py transcript.txt output/ [api_key]
```

---

### 🛠️ Utilità

#### `utils.py`
**Funzioni condivise:**
- `log_phase()` - Logging fasi di elaborazione
- `format_timestamp_srt()` - Formattazione timestamp SRT
- `get_video_info()` - Informazioni video con ffprobe

---

## 🚀 Utilizzo

### Metodo 1: Script Principale (Consigliato)
```bash
# Elaborazione completa
python video_silence_cutter.py video.mp4

# Con parametri personalizzati
python video_silence_cutter.py video.mp4 \
    --threshold -35 \
    --duration 0.3 \
    --whisper-model large

# Senza trascrizione/metadati AI
python video_silence_cutter.py video.mp4 --no-whisper
```

### Metodo 2: Moduli Individuali
Ogni modulo può essere eseguito standalone per test o debug.

---

## 📊 Flusso di Esecuzione

```
┌─────────────────────────────────────────────────────────┐
│                video_silence_cutter.py                  │
│                 (Orchestratore Principale)               │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   1. Verifica Dipendenze          │
        │   (flow_1_dependency_check.py)    │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   2. Estrazione Audio             │
        │   (flow_2_audio_extraction.py)    │
        │   - Separazione vocale AI         │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   3. Analisi Silenzi              │
        │   (flow_3_silence_analysis.py)    │
        │   - Rilevamento intervalli        │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   4. Trascrizione Whisper         │
        │   (flow_4_transcription.py)       │
        │   - Word-level timestamps         │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   5. Elaborazione Video           │
        │   (flow_5_video_processing.py)    │
        │   - Chunks, EDL, Sottotitoli      │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   6. Metadati AI                  │
        │   (flow_6_metadata_generation.py) │
        │   - Gemini AI, Thumbnail          │
        └───────────────────────────────────┘
```

---

## 🔧 Dipendenze

### Critiche (Obbligatorie)
- `ffmpeg` - Elaborazione audio/video
- `ffprobe` - Analisi metadata video

### Opzionali
- `openai-whisper` - Trascrizione AI
- `audio-separator` - Separazione vocale AI
- `google-generativeai` - Metadati e thumbnail AI
- `python-dotenv` - Gestione variabili ambiente

### Installazione
```bash
# Dipendenze Python
pip install openai-whisper audio-separator google-generativeai python-dotenv pillow

# FFmpeg (macOS)
brew install ffmpeg

# FFmpeg (Linux)
sudo apt-get install ffmpeg
```

---

## 📁 Struttura Output

```
output/
└── nome_video/
    ├── chunks/
    │   ├── c_0000.mp4
    │   ├── c_0001.mp4
    │   └── ...
    ├── premiere_pro.edl
    ├── subtitles.srt
    ├── subtitles.json
    ├── transcript.txt
    ├── metadata.txt
    ├── thumbnail.png
    ├── prompt.txt
    └── nome_video.mp4  (originale spostato)
```

---

## ✅ Vantaggi Architettura Modulare

1. **Manutenibilità** - Ogni modulo ha una responsabilità chiara
2. **Testabilità** - Ogni flusso può essere testato indipendentemente
3. **Riusabilità** - Moduli utilizzabili in altri progetti
4. **Debug facilitato** - Errori isolati per modulo
5. **Documentazione** - Codice più leggibile e documentato
6. **Scalabilità** - Facile aggiungere nuovi flussi

---

## 🐛 Debug e Test

### Test singolo modulo
```bash
# Test verifica dipendenze
python flow_1_dependency_check.py

# Test estrazione audio
python flow_2_audio_extraction.py test_video.mp4 test_audio.wav

# Test analisi silenzi
python flow_3_silence_analysis.py test_audio.wav

# Test trascrizione
python flow_4_transcription.py test_video.mp4
```

### Modalità verbose
Ogni modulo stampa informazioni dettagliate durante l'esecuzione.

---

## 📝 Note di Migrazione

Se hai script che usano il vecchio `video_silence_cutter.py`:

**✅ Compatibile:** L'interfaccia CLI rimane identica
```bash
# Funziona esattamente come prima
python video_silence_cutter.py video.mp4 --threshold -40
```

**⚠️ Se importi funzioni:** Aggiorna gli import
```python
# Vecchio
from video_silence_cutter import extract_audio

# Nuovo
from flow_2_audio_extraction import extract_audio
```

---

## 🤝 Contribuire

Per aggiungere un nuovo flusso:

1. Crea `flow_X_nome_flusso.py`
2. Implementa funzioni con docstring dettagliate
3. Aggiungi sezione `if __name__ == '__main__'` per test standalone
4. Importa nel file principale `video_silence_cutter.py`
5. Aggiorna questa documentazione

---

## 📄 Licenza

Stesso progetto originale.
