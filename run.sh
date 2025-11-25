#!/bin/bash

# Script unificato per Video Silence Cutter
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
    echo -e "${BLUE}     Video Silence Cutter${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
    echo -e "${YELLOW}Uso:${NC}"
    echo -e "  ./run.sh <video.mp4> [opzioni]"
    echo ""
    echo -e "${YELLOW}Esempi:${NC}"
    echo -e "  ${GREEN}./run.sh video.mp4${NC}                                  # Formato CCP"
    echo -e "  ${GREEN}./run.sh video.mp4 --format video${NC}                   # Formato video"
    echo -e "  ${GREEN}./run.sh video.mp4 --format total${NC}                   # CCP + video"
    echo -e "  ${GREEN}./run.sh video.mp4 -o output.mp4${NC}"
    echo -e "  ${GREEN}./run.sh video.mp4 --silence-thresh -35dB${NC}"
    echo -e "  ${GREEN}./run.sh video.mp4 --silence-duration 0.7${NC}"
    echo -e "  ${GREEN}./run.sh video.mp4 --no-subtitles${NC}"
    echo ""
    echo -e "${YELLOW}Opzioni disponibili:${NC}"
    python video_silence_cutter.py --help
    exit 0
fi

# Avvia il programma con tutti gli argomenti
echo -e "${GREEN}Avvio Video Silence Cutter...${NC}\n"
python video_silence_cutter.py "$@"
