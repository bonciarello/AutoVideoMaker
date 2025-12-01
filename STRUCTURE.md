# 📁 Struttura del Progetto - Video Silence Cutter

## 🎯 Nuova Organizzazione

Tutti i moduli di flusso sono stati spostati nella cartella **`src/`** per una migliore organizzazione.

```
ProjectVideoCutting-main/
│
├── video_silence_cutter.py          # ⭐ Orchestratore principale
│
├── src/                              # 📦 Moduli core
│   ├── __init__.py                   # Package initialization
│   ├── 1_dependency_check.py         # Verifica dipendenze
│   ├── 2_audio_extraction.py         # Estrazione e separazione audio
│   ├── 3_silence_analysis.py         # Analisi silenzi
│   ├── 4_transcription.py            # Trascrizione Whisper
│   ├── 5_video_processing.py         # Elaborazione video e export
│   ├── 6_metadata_generation.py      # Generazione metadati AI
│   └── utils.py                      # Funzioni condivise
│
├── 📚 Documentazione
│   ├── STRUCTURE.md                  # Questo file
│   ├── PROJECT_STRUCTURE.md          # Documentazione dettagliata
│   └── example_metadata.txt          # Esempio output metadati
│
├── 🚀 Script esecuzione
│   └── run.sh                        # Script bash
│
└── ⚙️ Configurazione
    ├── .env                          # Variabili ambiente
    └── requirements.txt              # Dipendenze Python
```

## 🔄 Flusso di Esecuzione

```
video_silence_cutter.py (root)
         │
         ├─> import src.utils
         ├─> import src.1_dependency_check
         ├─> import src.2_audio_extraction
         ├─> import src.3_silence_analysis
         ├─> import src.4_transcription
         ├─> import src.5_video_processing
         └─> import src.6_metadata_generation
```

## 📦 Dettaglio Moduli in `src/`

| File | Linee | Descrizione |
|------|-------|-------------|
| `1_dependency_check.py` | ~113 | Verifica ffmpeg, whisper, audio-separator, gemini |
| `2_audio_extraction.py` | ~180 | Estrazione audio + separazione vocale AI |
| `3_silence_analysis.py` | ~118 | Rilevamento intervalli di silenzio con FFmpeg |
| `4_transcription.py` | ~169 | Trascrizione Whisper + segmentazione intelligente |
| `5_video_processing.py` | ~191 | Taglio video, generazione EDL, export chunks |
| `6_metadata_generation.py` | ~219 | Metadati AI + thumbnail YouTube con Gemini |
| `utils.py` | ~40 | Funzioni condivise (log, timestamp, video info) |

**Totale:** ~1,030 linee di codice modulare

## 🚀 Come Usare

### Metodo Standard (Raccomandato)
```bash
# Dalla root del progetto
python3 video_silence_cutter.py video.mp4
```

### Test Singoli Moduli
```bash
# Entra nella cartella src
cd src

# Test verifica dipendenze
python3 1_dependency_check.py

# Test estrazione audio
python3 2_audio_extraction.py ../video.mp4 output_audio.wav

# Test analisi silenzi
python3 3_silence_analysis.py audio.wav

# Test trascrizione
python3 4_transcription.py ../video.mp4
```

## ✅ Vantaggi della Nuova Struttura

### Prima
```
ProjectVideoCutting-main/
├── video_silence_cutter.py (1009 linee monolitico)
├── flow_1_dependency_check.py
├── flow_2_audio_extraction.py
├── flow_3_silence_analysis.py
├── flow_4_transcription.py
├── flow_5_video_processing.py
├── flow_6_metadata_generation.py
└── utils.py
```

### Dopo ✨
```
ProjectVideoCutting-main/
├── video_silence_cutter.py (orchestratore pulito)
└── src/
    ├── 1_dependency_check.py
    ├── 2_audio_extraction.py
    ├── 3_silence_analysis.py
    ├── 4_transcription.py
    ├── 5_video_processing.py
    ├── 6_metadata_generation.py
    └── utils.py
```

### Benefici
1. ✅ **Organizzazione chiara** - Tutti i moduli in una cartella dedicata
2. ✅ **Nomi semplici** - Rimosso prefisso `flow_`, solo numeri + nome
3. ✅ **Namespace pulito** - Root contiene solo file essenziali
4. ✅ **Package Python** - `src/__init__.py` rende src un package importabile
5. ✅ **Scalabile** - Facile aggiungere `src/7_new_feature.py`

## 🔧 Import nei Tuoi Script

Se vuoi usare i moduli nei tuoi script:

```python
import sys
sys.path.insert(0, 'src')

# Import diretto
from utils import log_phase, get_video_info

# Import moduli numerici (usa importlib)
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Esempio
dep_check = load_module('dep_check', 'src/1_dependency_check.py')
dep_check.check_dependencies()
```

## 📊 Statistiche

- **File totali:** 8 (7 moduli + 1 orchestratore)
- **Linee totali:** ~1,243 linee
- **Modulo più grande:** `6_metadata_generation.py` (219 linee)
- **Modulo più piccolo:** `utils.py` (40 linee)
- **Media linee/modulo:** ~156 linee

## 🎯 Compatibilità

**100% retrocompatibile** con script esistenti che usano:
```bash
python3 video_silence_cutter.py [args]
```

Nessuna modifica necessaria al tuo workflow esistente!

---

Ultimo aggiornamento: 2025-12-01 | Versione: 2.0.0
