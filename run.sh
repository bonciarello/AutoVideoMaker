#!/bin/bash

# AutoVideoMaker - Unified script for automated video editing
# Automatic setup on first run, then fast execution

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
    export $(grep -v '^#' .env | xargs) 2>/dev/null
fi

# Funzione per il setup iniziale
setup_environment() {
    echo -e "${BLUE}====================================================================================================${NC}"
    echo -e "${BLUE}     AutoVideoMaker - Setup${NC}"
    echo -e "${BLUE}====================================================================================================${NC}\n"

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
    chmod +x main.py 2>/dev/null || true

    echo -e "${BLUE}====================================================================================================${NC}"
    echo -e "${GREEN}Setup completato con successo!${NC}"
    echo -e "${BLUE}====================================================================================================${NC}\n"
}

# Controlla se venv esiste, altrimenti fai setup
if [ ! -d "venv" ]; then
    setup_environment
fi

# Attiva virtual environment
source venv/bin/activate

# Installa/aggiorna dipendenze in ogni caso
echo -e "${YELLOW}Verificando dipendenze...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt > /dev/null 2>&1
    echo -e "${GREEN}✓ Dipendenze verificate e aggiornate${NC}\n"
fi

# Verifica che ci siano argomenti
if [ $# -eq 0 ]; then
    echo -e "${RED}Errore: Nessun file video specificato${NC}"
    echo -e "${YELLOW}Uso: $0 video.mp4 [opzioni]${NC}"
    echo -e "${YELLOW}     $0 *.mp4 [opzioni]${NC}"
    echo -e "${YELLOW}     $0 video1.mp4 video2.mp4 [opzioni]${NC}"
    exit 1
fi

# Esegui main.py (supporta video singoli e multipli)
python main.py "$@"