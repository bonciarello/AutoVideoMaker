#!/bin/bash

# Script unificato per Video Silence Cutter + AI Metadata Generator
# Setup automatico al primo avvio, poi esecuzione rapida

set -e  # Esci in caso di errore

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directory dello script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Carica variabili ambiente da .env se esiste
if [ -f ".env" ]; then
    echo -e "${BLUE}📄 Caricamento configurazione da .env...${NC}"
    export $(grep -v '^#' .env | xargs)
    echo -e "${GREEN}✓ Configurazione caricata${NC}\n"
fi

# Funzione per il setup iniziale
setup_environment() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}     Video Silence Cutter - Setup${NC}"
    echo -e "${BLUE}============================================================${NC}\n"

    # Verifica Python 3
    echo -e "${YELLOW}Verificando Python...${NC}"
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Errore: Python 3 non trovato!${NC}"
        echo "Installa Python 3 da https://www.python.org/downloads/"
        exit 1
    fi
    echo -e "${GREEN}✓ Python 3 trovato: $(python3 --version)${NC}\n"

    # Verifica FFmpeg
    echo -e "${YELLOW}Verificando FFmpeg...${NC}"
    if ! command -v ffmpeg &> /dev/null; then
        echo -e "${RED}Errore: FFmpeg non trovato!${NC}"
        echo "Installa FFmpeg con:"
        echo "  macOS:   brew install ffmpeg"
        echo "  Ubuntu:  sudo apt-get install ffmpeg"
        echo "  Windows: choco install ffmpeg"
        exit 1
    fi
    echo -e "${GREEN}✓ FFmpeg trovato${NC}\n"

    # Crea virtual environment
    echo -e "${YELLOW}Creando virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment creato${NC}\n"

    # Attiva virtual environment
    source venv/bin/activate

    # Aggiorna pip
    echo -e "${YELLOW}Aggiornando pip...${NC}"
    pip install --upgrade pip > /dev/null 2>&1
    echo -e "${GREEN}✓ Pip aggiornato${NC}\n"

    # Installa dipendenze
    echo -e "${YELLOW}Installando dipendenze...${NC}"
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo -e "${GREEN}✓ Dipendenze installate${NC}\n"
    else
        echo -e "${RED}Errore: requirements.txt non trovato!${NC}"
        exit 1
    fi

    # Rendi eseguibile lo script Python
    chmod +x video_silence_cutter.py 2>/dev/null || true

    echo -e "${BLUE}============================================================${NC}"
    echo -e "${GREEN}Setup completato con successo!${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

# Controlla se venv esiste, altrimenti fai setup
if [ ! -d "venv" ]; then
    setup_environment
fi

# Attiva virtual environment
source venv/bin/activate

# Se non ci sono argomenti, mostra l'help
if [ $# -eq 0 ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}     Video Silence Cutter + AI Metadata Generator${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
    echo -e "${YELLOW}Uso:${NC}"
    echo -e "  ./run.sh <video.mp4> [opzioni]"
    echo ""
    echo -e "${YELLOW}Esempi:${NC}"
    echo -e "  ${GREEN}./run.sh video.mp4${NC}                                  # Processing completo + metadati AI"
    echo -e "  ${GREEN}./run.sh video.mp4 --whisper-model large${NC}            # Con modello Whisper large"
    echo -e "  ${GREEN}./run.sh video.mp4 -t -35 -d 0.7${NC}                    # Soglia e durata silenzi custom"
    echo ""
    echo -e "${YELLOW}Features:${NC}"
    echo -e "  • Rilevamento e taglio automatico dei silenzi"
    echo -e "  • Separazione vocale AI per migliore precisione"
    echo -e "  • Generazione sottotitoli con Whisper AI"
    echo -e "  • Export chunks, EDL, video finale"
    echo -e "  • Generazione automatica metadati con Google Gemini AI"
    echo ""
    echo -e "${YELLOW}Configurazione:${NC}"
    echo -e "  • Crea file .env (copia da .env.example)"
    echo -e "  • Aggiungi: GEMINI_API_KEY=your-key-here"
    echo ""
    echo -e "${YELLOW}Opzioni disponibili:${NC}"
    python video_silence_cutter.py --help
    exit 0
fi

# Estrai il file video dal primo argomento
VIDEO_FILE="$1"

# Verifica che il video esista
if [ ! -f "$VIDEO_FILE" ]; then
    echo -e "${RED}❌ Errore: File non trovato: $VIDEO_FILE${NC}"
    exit 1
fi

# Estrai nome del video (senza estensione)
VIDEO_NAME=$(basename "$VIDEO_FILE" | sed 's/\.[^.]*$//')
OUTPUT_DIR="output/${VIDEO_NAME}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Video Processing + AI Metadata Generator              ║${NC}"
echo -e "${BLUE}║                                                                ║${NC}"
echo -e "${BLUE}║  1. Taglia silenzi dal video                                   ║${NC}"
echo -e "${BLUE}║  2. Genera sottotitoli con Whisper                             ║${NC}"
echo -e "${BLUE}║  3. Genera metadati con Google Gemini AI                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📹 Video: $VIDEO_FILE${NC}"
echo -e "${YELLOW}📁 Output: $OUTPUT_DIR${NC}"
echo ""

# STEP 1: Processa il video
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}STEP 1/2: Processing Video${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

python video_silence_cutter.py "$@"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Errore durante il processing del video${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Video processato con successo!${NC}"
echo ""

# STEP 2: Genera metadati AI (se API key presente)
if [ -n "$GEMINI_API_KEY" ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}STEP 2/2: Generazione Metadati AI${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    TRANSCRIPT_FILE="${OUTPUT_DIR}/${VIDEO_NAME}_tagliato_transcript.txt"

    if [ ! -f "$TRANSCRIPT_FILE" ]; then
        echo -e "${RED}❌ Errore: Trascrizione non trovata: $TRANSCRIPT_FILE${NC}"
        exit 1
    fi

    python generate_video_metadata.py "$TRANSCRIPT_FILE" --api-key "$GEMINI_API_KEY"

    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Errore durante la generazione dei metadati${NC}"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}✅ Metadati generati con successo!${NC}"
else
    echo -e "${YELLOW}⚠️  Chiave API Gemini non trovata, skip generazione metadati${NC}"
    echo -e "${YELLOW}   Per generare metadati, crea un file .env con:${NC}"
    echo -e "${YELLOW}     GEMINI_API_KEY=your-key-here${NC}"
fi

# Riepilogo finale
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ COMPLETATO!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}📂 File generati in: ${OUTPUT_DIR}/${NC}"
echo ""
echo "   📹 Video finale:"
echo "      └─ FINAL_${VIDEO_NAME}_tagliato.mp4"
echo ""
echo "   📄 Sottotitoli:"
echo "      ├─ ${VIDEO_NAME}_tagliato.srt"
echo "      ├─ ${VIDEO_NAME}_tagliato_subtitles.json"
echo "      └─ ${VIDEO_NAME}_tagliato_transcript.txt"
echo ""

if [ -n "$GEMINI_API_KEY" ]; then
    echo "   🤖 Metadati AI:"
    echo "      ├─ ${VIDEO_NAME}_tagliato_metadata.txt"
    echo "      └─ ${VIDEO_NAME}_tagliato_thumbnail.png (1920x1080)"
    echo ""
fi

echo "   🎬 Chunks (segmenti):"
echo "      └─ chunks/"
echo ""
echo "   🎞️  EDL (Premiere Pro):"
echo "      └─ ${VIDEO_NAME}_tagliato.edl"
echo ""