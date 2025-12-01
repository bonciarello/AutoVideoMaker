# 📦 Moduli Core - Video Silence Cutter

Questa cartella contiene tutti i moduli core per l'elaborazione video.

## 📋 Indice Moduli

| # | Modulo | Descrizione | Standalone |
|---|--------|-------------|------------|
| 1 | `1_dependency_check.py` | Verifica dipendenze di sistema | ✅ |
| 2 | `2_audio_extraction.py` | Estrazione e separazione audio AI | ✅ |
| 3 | `3_silence_analysis.py` | Rilevamento intervalli di silenzio | ✅ |
| 4 | `4_transcription.py` | Trascrizione Whisper AI | ✅ |
| 5 | `5_video_processing.py` | Elaborazione video e export | ✅ |
| 6 | `6_metadata_generation.py` | Generazione metadati e thumbnail AI | ✅ |
| - | `utils.py` | Funzioni condivise | ❌ |

## 🚀 Esecuzione Standalone

Ogni modulo può essere eseguito indipendentemente per test:

```bash
# 1. Verifica dipendenze
python3 1_dependency_check.py

# 2. Estrai audio
python3 2_audio_extraction.py ../video.mp4 output.wav

# 3. Analizza silenzi
python3 3_silence_analysis.py audio.wav

# 4. Trascrivi
python3 4_transcription.py ../video.mp4 output.srt

# 5. Elabora video (richiede file JSON con tagli)
python3 5_video_processing.py ../video.mp4 cuts.json ../output/

# 6. Genera metadati (richiede trascrizione)
python3 6_metadata_generation.py transcript.txt ../output/ [api_key]
```

## 🔗 Dipendenze tra Moduli

```
utils.py
  └─> Usato da: tutti i moduli

1_dependency_check.py
  └─> Indipendente

2_audio_extraction.py
  └─> Indipendente

3_silence_analysis.py
  └─> Usa: utils.py

4_transcription.py
  └─> Usa: utils.py

5_video_processing.py
  ├─> Usa: utils.py
  └─> Usa: 4_transcription.py

6_metadata_generation.py
  └─> Usa: utils.py
```

## 📝 Convenzioni

### Naming
- **Moduli numerici:** `{numero}_{nome_flusso}.py`
- **Funzioni principali:** Nome descrittivo (es. `extract_audio`)
- **Helper functions:** Prefisso underscore se private

### Docstrings
Ogni funzione pubblica ha docstring con:
- Descrizione breve
- `:param nome: descrizione` per ogni parametro
- `:return: descrizione` del valore di ritorno

### Esempio
```python
def extract_audio(video_path: str, output_audio: str) -> Optional[str]:
    """
    Estrae l'audio dal video con separazione vocale opzionale.

    :param video_path: Percorso del video
    :param output_audio: Percorso output audio WAV
    :return: Percorso vocals o None
    """
```

## 🧪 Testing

Per testare un modulo:
1. Aggiungi `if __name__ == '__main__':` block
2. Implementa test basilari con args da CLI
3. Verifica import e dipendenze

## 🔧 Import nei Tuoi Script

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import semplici
from utils import log_phase, get_video_info

# Import moduli numerici (usa importlib)
import importlib.util

spec = importlib.util.spec_from_file_location('dep', 'src/1_dependency_check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

module.check_dependencies()
```

## 📊 Statistiche Moduli

| Modulo | Linee | Funzioni | Dipendenze Esterne |
|--------|-------|----------|-------------------|
| 1_dependency_check.py | 113 | 7 | subprocess |
| 2_audio_extraction.py | 180 | 3 | ffmpeg, audio-separator |
| 3_silence_analysis.py | 118 | 3 | ffmpeg |
| 4_transcription.py | 169 | 5 | openai-whisper |
| 5_video_processing.py | 191 | 6 | ffmpeg |
| 6_metadata_generation.py | 219 | 4 | google-generativeai, PIL |
| utils.py | 40 | 3 | json, pathlib, subprocess |
| **TOTALE** | **1,030** | **31** | - |

## ⚙️ Configurazione

Alcuni moduli richiedono configurazione:

### `6_metadata_generation.py`
Richiede `GEMINI_API_KEY` in `.env`:
```bash
# .env nella root del progetto
GEMINI_API_KEY=your_api_key_here
```

### `4_transcription.py`
Puoi configurare il modello Whisper:
- `tiny` - Veloce, meno preciso
- `base` - Bilanciato
- `small` - Buono
- `medium` - Consigliato (default)
- `large` - Massima precisione

## 🤝 Contribuire

Per aggiungere un nuovo modulo:
1. Crea `src/7_nome_nuovo_flusso.py`
2. Segui le convenzioni esistenti
3. Aggiungi docstrings
4. Implementa `if __name__ == '__main__'` per test
5. Aggiorna questa documentazione
6. Importa in `../video_silence_cutter.py`

---

Generato automaticamente | Versione: 2.0.0
