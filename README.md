# Video Silence Cutter

Script Python che analizza automaticamente un video, identifica le parti di silenzio tramite analisi audio e sottotitoli, e genera un progetto CapCut (.ccp) con i tagli già applicati.

## Caratteristiche

- **Riduzione del rumore** - Filtra automaticamente rumori di fondo prima dell'analisi per risultati più precisi
- **Rilevamento automatico dei silenzi** tramite analisi audio con soglia personalizzabile
- **Generazione sottotitoli** con Whisper AI per identificare pause nel parlato
- **Unione intelligente** degli intervalli di silenzio vicini
- **Formati multipli** - Esporta come video MP4, file EDL o progetto CapCut
- **Report dettagliato** del tempo risparmiato

## Requisiti

### Software necessario

1. **Python 3.8+**
2. **FFmpeg** - Per l'elaborazione audio/video
   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # Windows (con Chocolatey)
   choco install ffmpeg
   ```

### Librerie Python

Le dipendenze includono:
- **openai-whisper** - Per la generazione automatica di sottotitoli
- **numpy** - Elaborazione numerica
- **imageio**, **psutil**, **json5** - Per il supporto CapCutAPI/pyJianYingDraft

Installa tutte le dipendenze con:

```bash
pip install -r requirements.txt
```

## Installazione e Avvio Rapido

### Metodo 1: Script automatico (Consigliato)

Lo script automatico configura tutto per te:

```bash
# Rendi eseguibile lo script (solo la prima volta)
chmod +x setup_and_run.sh

# Avvia il setup automatico
./setup_and_run.sh
```

Lo script:
- Verifica che Python 3 e FFmpeg siano installati
- Crea automaticamente un virtual environment
- Installa tutte le dipendenze necessarie
- Ti guida nell'elaborazione del primo video

### Metodo 2: Installazione manuale

1. Clona o scarica questo progetto
2. Installa FFmpeg (vedi sopra)
3. Crea un virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Su Windows: venv\Scripts\activate
   ```
4. Installa le dipendenze Python:
   ```bash
   pip install -r requirements.txt
   ```

## Utilizzo

### Utilizzo rapido con script

Dopo il primo setup, usa lo script rapido:

```bash
# Utilizzo base
./run.sh video.mp4

# Con opzioni
./run.sh video.mp4 -o output.ccp --threshold -35
```

### Utilizzo diretto Python

```bash
# Attiva il virtual environment (se non già attivo)
source venv/bin/activate

# Utilizzo base
python video_silence_cutter.py video.mp4
```

Questo genererà un file `video_tagliato.ccp` nella stessa directory.

### Opzioni avanzate

```bash
python video_silence_cutter.py video.mp4 \
  -o output_project.ccp \
  --threshold -35 \
  --duration 0.7 \
  --merge 1.5
```

### Parametri disponibili

- `input_video`: Percorso del video di input (obbligatorio)
- `-o, --output`: Percorso del file progetto CapCut (.ccp) di output (default: `{nome_video}_tagliato.ccp`)
- `-t, --threshold`: Soglia di silenzio in dB (default: -40)
  - Valori più alti (es. -30) rilevano solo silenzi più profondi
  - Valori più bassi (es. -50) rilevano anche rumori di fondo bassi
- `-d, --duration`: Durata minima del silenzio in secondi (default: 0.5)
  - Pause più brevi verranno ignorate
- `-m, --merge`: Distanza massima in secondi per unire silenzi vicini (default: 1.0)
  - Silenzi separati da meno di questo valore verranno uniti
- `--format`: Formato di output (default: video)
  - `video`: Video MP4 già tagliato
  - `edl`: File EDL per editor professionali
  - `ccp`: Progetto CapCut nativo (consigliato per CapCut)
  - `total`: Genera sia progetto CCP che video MP4
- `--no-subtitles`: Non genera sottotitoli (più veloce ma meno preciso)
- `--no-noise-reduction`: Disattiva la riduzione del rumore (default: attiva)
  - La riduzione del rumore migliora la precisione del rilevamento silenzi
  - Filtra rumori sotto 200Hz e sopra 3000Hz (mantiene solo la voce umana)

## Esempi

### Genera video MP4 tagliato (default)

```bash
./run.sh tutorial.mp4
# Output: tutorial_tagliato.mp4
```

### Video tutorial/educativo (voce continua)

```bash
./run.sh tutorial.mp4 --threshold -35 --duration 0.8
```

### Podcast o intervista (pause più lunghe)

```bash
./run.sh podcast.mp4 --threshold -40 --duration 1.0 --merge 2.0
```

### Genera file EDL per Premiere Pro

```bash
./run.sh video.mp4 --format edl
# Output: video_tagliato.edl
```

### Elaborazione veloce senza sottotitoli

```bash
./run.sh video.mp4 --no-subtitles
```

### Video con molto rumore di fondo

```bash
# La riduzione del rumore è già attiva di default
./run.sh video_rumoroso.mp4 --threshold -35
```

### Disattivare la riduzione del rumore (se causa problemi)

```bash
./run.sh video.mp4 --no-noise-reduction
```

### Genera sia progetto CapCut che video MP4

```bash
./run.sh video.mp4 --format total
# Output: video_tagliato/ (progetto CapCut) + video_tagliato.mp4
```

## Formati di Output

Lo script supporta 4 formati di output:

### 1. Progetto CapCut (Consigliato) - `--format ccp`

Genera un progetto CapCut nativo usando la libreria **pyJianYingDraft** da CapCutAPI. I video vengono aggiunti automaticamente alla timeline con i tagli già applicati.

```bash
./run.sh video.mp4 --format ccp
# Output: video_tagliato/ (cartella progetto CapCut)
```

**Vantaggi:**
- ✅ Il progetto appare automaticamente in CapCut Desktop (se esportato nella directory corretta)
- ✅ Video già tagliato nella timeline con segmenti separati
- ✅ Formato nativo CapCut con supporto completo a tutte le funzionalità
- ✅ Basato su pyJianYingDraft da [CapCutAPI](https://github.com/sun-guannan/CapCutAPI)

**Come usarlo:**
1. Genera il progetto con `--format ccp`
2. Se esportato in `~/Movies/CapCut/User Data/Projects/com.lveditor.draft/`, il progetto apparirà automaticamente in CapCut
3. Altrimenti, usa File → Open Project in CapCut per aprirlo
4. Il video è già nella timeline con i segmenti video tagliati!

### 2. Video MP4 - `--format video`

Genera direttamente un video MP4 con i silenzi già rimossi. Questo è il metodo più semplice e compatibile con qualsiasi editor video.

```bash
./run.sh video.mp4 --format video
# Output: video_tagliato.mp4 (pronto da usare!)
```

**Vantaggi:**
- ✅ Funziona immediatamente, nessuna importazione necessaria
- ✅ Compatibile con CapCut, Premiere Pro, DaVinci Resolve, etc.
- ✅ Puoi importarlo direttamente in CapCut e aggiungere effetti
- ✅ **Mantiene codec e caratteristiche originali** (qualità, bitrate, fps)
- ✅ Rilevamento automatico codec (H.264, H.265/HEVC, VP8, VP9, etc.)
- ✅ Nessuna configurazione aggiuntiva richiesta

### 3. File EDL - `--format edl`

Genera un file EDL (Edit Decision List) compatibile con editor professionali come Premiere Pro, DaVinci Resolve, Final Cut Pro.

```bash
./run.sh video.mp4 --format edl
# Output: video_tagliato.edl
```

**Come usare:**
1. Apri il tuo editor video (Premiere, DaVinci, etc.)
2. Importa il video originale
3. Importa il file EDL generato
4. L'editor applicherà automaticamente tutti i tagli

### 4. Formato Total (Completo) - `--format total`

Genera **sia** il progetto CapCut **che** il video MP4 tagliato. Ideale quando vuoi avere entrambi i formati per massima flessibilità.

```bash
./run.sh video.mp4 --format total
# Output:
#   - video_tagliato/ (progetto CapCut)
#   - video_tagliato.mp4 (video già tagliato)
```

**Vantaggi:**
- ✅ Hai sia il progetto editabile che il video finale
- ✅ Puoi modificare in CapCut o usare direttamente il video
- ✅ Nessuna scelta da fare, ottieni tutto!

## Come funziona

1. **Estrazione audio**: Lo script estrae l'audio dal video in formato WAV
2. **Riduzione del rumore**: Applica filtri audio avanzati per rimuovere rumori di fondo
   - High-pass filter (200Hz): Rimuove rumori bassi
   - Low-pass filter (3000Hz): Rimuove rumori alti, mantiene voce umana
   - FFT Denoiser: Riduce rumori ambientali
   - Non-local means denoiser: Riduzione rumore intelligente
   - Normalizzazione volume: Uniforma i livelli audio
3. **Analisi silenzi**: Utilizza FFmpeg per rilevare gli intervalli di silenzio sull'audio pulito
4. **Generazione sottotitoli** (opzionale): Usa Whisper AI per trascrivere l'audio e identificare le pause nel parlato
5. **Unione intervalli**: Combina gli intervalli di silenzio vicini
6. **Calcolo segmenti**: Determina quali parti del video mantenere
7. **Generazione output**: Crea il file nel formato scelto (video/EDL/CCP)

## Come usare l'output con CapCut

### Metodo 1: Video MP4 (Più semplice)

1. Esegui: `./run.sh video.mp4 --format video`
2. Apri CapCut Desktop
3. Trascina il file `video_tagliato.mp4` nella timeline
4. Il video è già tagliato! Aggiungi effetti, transizioni, etc.
5. Esporta il risultato finale

### Metodo 2: File EDL (Per editor professionali)

Se usi editor come Premiere Pro o DaVinci Resolve:

1. Esegui: `./run.sh video.mp4 --format edl`
2. Apri il tuo editor
3. Importa il video originale nel progetto
4. File → Import → EDL → Seleziona `video_tagliato.edl`
5. I tagli vengono applicati automaticamente

### Metodo 3: Progetto CapCut (Automatico!)

Il modo più semplice - il progetto appare automaticamente in CapCut:

1. Esegui: `./run.sh video.mp4 --format ccp`
2. Apri CapCut Desktop
3. **Il progetto apparirà automaticamente nella lista!**
4. Clicca sul progetto per aprirlo

**Come funziona:**
- Il progetto viene salvato direttamente in `~/Movies/CapCut/User Data/Projects/com.lveditor.draft/`
- CapCut scansiona automaticamente questa cartella
- Nessuna importazione manuale necessaria!

**Struttura della cartella:**
- `draft_info.json` - Configurazione principale
- `draft_meta_info.json` - Metadati del progetto
- `draft_settings` - Impostazioni
- Sottocartelle necessarie (Resources, etc.)

## Output

Lo script fornisce un report dettagliato:

```
============================================================
Video Silence Cutter
============================================================
Video: tutorial.mp4
Durata: 600.00s
============================================================

Estraendo audio da tutorial.mp4...
Analizzando silenzi nell'audio (soglia: -40dB, durata minima: 0.5s)...
Trovati 25 intervalli di silenzio
Generando sottotitoli con Whisper...

Intervalli di silenzio da rimuovere: 20
  1. 5.23s - 7.45s (durata: 2.22s)
  2. 15.67s - 17.12s (durata: 1.45s)
  ...

Segmenti da mantenere: 21

Progetto CapCut generato con successo!
Durata originale: 600.00s
Durata dopo taglio: 485.50s
Tempo risparmiato: 114.50s (19.1%)
============================================================
```

## Dettagli tecnici

### Formato Video MP4
- Codec video: H.264 (libx264) con CRF 23
- Codec audio: AAC a 192kbps
- Mantiene risoluzione e framerate originali
- Compatibile universalmente

### Formato EDL
- Standard CMX 3600
- Timecode in formato HH:MM:SS:FF
- Compatibile con Premiere Pro, DaVinci Resolve, Final Cut Pro, Avid

### Formato Progetto CapCut
CapCut usa una cartella di progetto con struttura specifica:
- `draft_info.json` - Configurazione principale (canvas, materiali, tracce)
- `draft_meta_info.json` - Metadati e percorsi
- `draft_settings` - Impostazioni del progetto
- Sottocartelle: Resources, adjust_mask, common_attachment, etc.
- Compatibile con CapCut Desktop 7.4.0 e versioni successive

## Limitazioni

- I sottotitoli sono in italiano (modificabile nel codice cambiando `language="it"` in `language="en"`)
- Il progetto CapCut generato è una struttura vuota (bisogna importare manualmente il video originale)
- Per semplicità d'uso, si consiglia il formato `video` (MP4)

## Troubleshooting

### "ffmpeg non è installato"
Installa FFmpeg seguendo le istruzioni nella sezione Requisiti.

### "openai-whisper non è installato"
Esegui: `pip install openai-whisper` o usa l'opzione `--no-subtitles`

### Il progetto CapCut non si apre
Assicurati di:
- Aprire la **cartella** del progetto, non un singolo file
- Usare CapCut Desktop 7.4.0 o superiore
- Se non funziona, usa `--format video` per generare un MP4 già tagliato

### Il video generato ha problemi di qualità
Modifica i parametri FFmpeg nel codice alla riga 210:
- `-crf 23`: abbassa per qualità migliore (es. 18), alza per file più piccoli (es. 28)
- `-preset medium`: usa `slow` per qualità migliore o `fast` per velocità

### Troppi/pochi tagli
Regola i parametri:
- `--threshold`: aumenta per tagliare meno, diminuisci per tagliare di più
- `--duration`: aumenta per ignorare pause brevi
- `--merge`: aumenta per unire più silenzi insieme

### La riduzione del rumore causa problemi
Se l'audio viene distorto o i silenzi non vengono rilevati correttamente:
```bash
./run.sh video.mp4 --no-noise-reduction
```

### Audio con molto rumore ambientale non rileva i silenzi
La riduzione del rumore aiuta molto in questi casi (è già attiva di default). Prova anche ad aumentare la soglia:
```bash
./run.sh video.mp4 --threshold -35
```

## Dettagli Tecnici

### Integrazione CapCutAPI

Il progetto utilizza la libreria **pyJianYingDraft** dal repository [CapCutAPI](https://github.com/sun-guannan/CapCutAPI) per generare progetti CapCut nativi.

**Architettura:**
- [capcut_wrapper.py](capcut_wrapper.py) - Wrapper semplificato per pyJianYingDraft
- [pyJianYingDraft/](pyJianYingDraft/) - Libreria copiata da CapCutAPI
- [settings/](settings/) - Configurazioni CapCutAPI
- [capcut_api_lib/template/](capcut_api_lib/template/) - Template struttura progetto CapCut

**Funzionalità:**
- `CapCutProjectBuilder` - Classe per costruire progetti CapCut
- `add_video_segments()` - Aggiunge segmenti video alla timeline
- `save_to_capcut_folder()` - Salva progetto nella directory CapCut

**Conversione formato temporale:**
- CapCut usa microsecondi internamente (1s = 1,000,000μs)
- I segmenti vengono convertiti automaticamente da secondi a microsecondi
- Ogni segmento ha `source_timerange` (nel video originale) e `target_timerange` (nella timeline)

### Export Video (MP4)

L'export video mantiene le caratteristiche originali del file:

**Rilevamento automatico codec:**
- Video: H.264, H.265/HEVC, VP8, VP9, MPEG-4
- Audio: AAC, MP3, Vorbis, Opus
- Bitrate audio preservato dal file originale

**Qualità:**
- CRF 18 per H.264/H.265 (quasi lossless)
- Preset: medium (bilanciamento velocità/qualità)
- Fallback automatico a libx264+aac se codec non supportato

**Codec supportati:**
```
Video: h264→libx264, h265/hevc→libx265, vp8→libvpx, vp9→libvpx-vp9
Audio: aac (nativo), mp3→libmp3lame, vorbis→libvorbis, opus→libopus
```

## Licenza

Questo progetto è open source e disponibile per uso personale e commerciale.

## Contributi

Contributi, bug report e feature request sono benvenuti!
