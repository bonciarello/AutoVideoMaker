# 📁 Struttura del Progetto

## File Principali

```
ProjectVideoCutting-main/
│
├── 🎯 video_silence_cutter.py          # Orchestratore principale
│
├── 📦 MODULI DI FLUSSO:
│   ├── flow_1_dependency_check.py      # Verifica dipendenze
│   ├── flow_2_audio_extraction.py      # Estrazione e separazione audio
│   ├── flow_3_silence_analysis.py      # Analisi silenzi
│   ├── flow_4_transcription.py         # Trascrizione Whisper
│   ├── flow_5_video_processing.py      # Elaborazione video e export
│   └── flow_6_metadata_generation.py   # Generazione metadati AI
│
├── 🛠️  utils.py                         # Funzioni condivise
│
├── 📚 DOCUMENTAZIONE:
│   ├── MODULES_README.md               # Documentazione moduli
│   ├── PROJECT_STRUCTURE.md            # Questo file
│   └── example_metadata.txt            # Esempio output metadati
│
├── 🚀 SCRIPT ESECUZIONE:
│   └── run.sh                          # Script bash per esecuzione
│
└── ⚙️  CONFIGURAZIONE:
    ├── .env                            # Variabili ambiente (GEMINI_API_KEY)
    ├── .gitignore
    └── requirements.txt                # Dipendenze Python
```

## 🔄 Flusso di Esecuzione

```
┌────────────────────────────────────────────────────────────────┐
│                    video_silence_cutter.py                     │
│                  (Punto di ingresso principale)                 │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ import
                              ▼
        ┌─────────────────────────────────────────┐
        │              utils.py                   │
        │  (log_phase, get_video_info, etc.)      │
        └─────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Flow 1     │    │   Flow 2     │    │   Flow 3     │
│ Dependencies │───▶│    Audio     │───▶│   Silence    │
│    Check     │    │  Extraction  │    │   Analysis   │
└──────────────┘    └──────────────┘    └──────────────┘
                                                │
                    ┌───────────────────────────┘
                    │
                    ▼
        ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
        │   Flow 4     │───▶│   Flow 5     │───▶│   Flow 6     │
        │Transcription │    │    Video     │    │   Metadata   │
        │  (Whisper)   │    │  Processing  │    │ (Gemini AI)  │
        └──────────────┘    └──────────────┘    └──────────────┘
```

## 📊 Dettaglio File

### 🎯 File Principale

#### `video_silence_cutter.py` (204 linee)
- **Scopo:** Orchestratore che coordina tutti i flussi
- **Dipendenze:** Importa tutti i moduli flow_*
- **CLI:** Argomenti da riga di comando
- **Output:** Coordina generazione di tutti gli output

---

### 📦 Moduli di Flusso

#### `flow_1_dependency_check.py` (~113 linee)
- **Funzioni:** 7
- **Dipendenze esterne:** subprocess
- **Standalone:** ✅ Eseguibile indipendentemente
- **Test:** `python3 flow_1_dependency_check.py`

#### `flow_2_audio_extraction.py` (~180 linee)
- **Funzioni:** 3 principali
- **Dipendenze esterne:** ffmpeg, audio-separator (opzionale)
- **Standalone:** ✅ Eseguibile indipendentemente
- **Test:** `python3 flow_2_audio_extraction.py video.mp4 audio.wav`

#### `flow_3_silence_analysis.py` (~118 linee)
- **Funzioni:** 3
- **Dipendenze esterne:** ffmpeg
- **Standalone:** ✅ Eseguibile indipendentemente
- **Test:** `python3 flow_3_silence_analysis.py audio.wav`

#### `flow_4_transcription.py` (~169 linee)
- **Funzioni:** 5
- **Dipendenze esterne:** openai-whisper
- **Import interni:** utils.format_timestamp_srt
- **Standalone:** ✅ Eseguibile indipendentemente
- **Test:** `python3 flow_4_transcription.py video.mp4`

#### `flow_5_video_processing.py` (~191 linee)
- **Funzioni:** 6
- **Dipendenze esterne:** ffmpeg
- **Import interni:** utils, flow_4_transcription
- **Standalone:** ✅ Eseguibile indipendentemente
- **Test:** `python3 flow_5_video_processing.py video.mp4 cuts.json output/`

#### `flow_6_metadata_generation.py` (~219 linee)
- **Funzioni:** 4 principali
- **Dipendenze esterne:** google-generativeai, PIL
- **Import interni:** utils.log_phase
- **Standalone:** ✅ Eseguibile indipendentemente
- **Test:** `python3 flow_6_metadata_generation.py transcript.txt output/`

---

### 🛠️ Utilità

#### `utils.py` (~40 linee)
- **Funzioni:** 3
- **Scopo:** Funzioni condivise tra moduli
- **Dipendenze:** json, pathlib, subprocess

---

## 📈 Metriche del Progetto

### Linee di Codice
- **Totale originale:** ~1009 linee (video_silence_cutter.py)
- **Totale modulare:** ~1233 linee (distribuito in 8 file)
- **Aumento:** +224 linee (+22% per maggiore documentazione e modularità)

### Distribuzione
| Modulo | Linee | Percentuale |
|--------|-------|-------------|
| flow_5_video_processing.py | ~191 | 15.5% |
| flow_6_metadata_generation.py | ~219 | 17.8% |
| video_silence_cutter.py | ~204 | 16.5% |
| flow_2_audio_extraction.py | ~180 | 14.6% |
| flow_4_transcription.py | ~169 | 13.7% |
| flow_3_silence_analysis.py | ~118 | 9.6% |
| flow_1_dependency_check.py | ~113 | 9.2% |
| utils.py | ~40 | 3.2% |

### Complessità
- **Funzioni totali:** ~35
- **Moduli indipendenti:** 6
- **Dipendenze esterne:** 6 (ffmpeg, whisper, audio-separator, gemini, PIL, dotenv)

---

## 🚀 Come Usare

### Metodo Standard
```bash
python3 video_silence_cutter.py video.mp4
```

### Test Singoli Moduli
```bash
# Verifica dipendenze
python3 flow_1_dependency_check.py

# Estrai audio
python3 flow_2_audio_extraction.py video.mp4 audio.wav

# Analizza silenzi
python3 flow_3_silence_analysis.py audio.wav

# Trascrivi
python3 flow_4_transcription.py video.mp4
```

---

## ✅ Vantaggi Nuova Struttura

### Prima (Monolitico)
```python
video_silence_cutter.py (1009 linee)
├── Tutte le funzioni mescolate
├── Difficile manutenzione
├── Testing complesso
└── Riuso impossibile
```

### Dopo (Modulare)
```python
video_silence_cutter.py (204 linee) ← Orchestratore
├── flow_1_dependency_check.py ← Riusabile
├── flow_2_audio_extraction.py ← Riusabile
├── flow_3_silence_analysis.py ← Riusabile
├── flow_4_transcription.py ← Riusabile
├── flow_5_video_processing.py ← Riusabile
└── flow_6_metadata_generation.py ← Riusabile
```

### Benefici Concreti
1. ✅ **Debugging facilitato:** Errore in Flow 3? Guarda solo quel file
2. ✅ **Test isolati:** Ogni modulo testabile indipendentemente
3. ✅ **Riuso:** Usa flow_4_transcription.py in altri progetti
4. ✅ **Onboarding:** Nuovo developer capisce un modulo alla volta
5. ✅ **Manutenzione:** Modifica una feature senza toccare il resto
6. ✅ **Scalabilità:** Aggiungi flow_7_new_feature.py facilmente

---

## 🔄 Compatibilità Retroattiva

**100% compatibile** con script esistenti che usano:
```bash
python3 video_silence_cutter.py [args]
```

**Se importi funzioni:**
```python
# Prima
from video_silence_cutter import extract_audio

# Dopo
from flow_2_audio_extraction import extract_audio
```

---

## 📝 Prossimi Passi Suggeriti

1. ✅ ~~Dividere codice in moduli~~
2. ✅ ~~Creare documentazione~~
3. ⏳ Aggiungere unit test per ogni modulo
4. ⏳ Creare CI/CD pipeline
5. ⏳ Aggiungere type hints completi
6. ⏳ Creare GUI wrapper (opzionale)
7. ⏳ Dockerizzare applicazione

---

## 🤝 Contribuire

Per aggiungere un nuovo flusso:

1. Crea `flow_7_nome_flusso.py`
2. Segui pattern esistenti
3. Aggiungi docstring dettagliate
4. Implementa `if __name__ == '__main__'` per test
5. Importa in `video_silence_cutter.py`
6. Aggiorna documentazione

---

Generato automaticamente | Ultima modifica: 2025-12-01
