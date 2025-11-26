#!/usr/bin/env python3
"""
Video Metadata Generator
Analizza i sottotitoli usando Google Gemini API e genera metadati per il video.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Optional


def load_transcript(transcript_path: str) -> str:
    """
    Carica la trascrizione dal file TXT.

    :param transcript_path: Percorso del file di trascrizione
    :return: Testo completo della trascrizione
    """
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ Errore: File non trovato: {transcript_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Errore durante la lettura del file: {e}")
        sys.exit(1)


def analyze_with_gemini(transcript: str, api_key: str) -> Dict[str, str]:
    """
    Analizza la trascrizione usando Google Gemini API.

    :param transcript: Testo completo della trascrizione
    :param api_key: Chiave API di Google Gemini
    :return: Dict con titolo, descrizione e prompt immagine
    """
    try:
        import google.generativeai as genai

        # Configura Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-3-pro-preview')

        # Prompt per l'analisi
        prompt = f"""Analizza la seguente trascrizione di un video e genera:

1. **TITOLO**: Un titolo accattivante e SEO-friendly per il video (max 70 caratteri)
2. **DESCRIZIONE**: Una descrizione dettagliata del contenuto del video (200-300 parole)
3. **PROMPT_IMMAGINE**: Un prompt dettagliato in inglese per generare un'immagine di copertina usando un modello AI text-to-image. Il prompt deve essere descrittivo, specifico e adatto a Stable Diffusion / DALL-E.

Formato della risposta (JSON):
{{
  "titolo": "...",
  "descrizione": "...",
  "prompt_immagine": "..."
}}

TRASCRIZIONE:
{transcript}

Rispondi SOLO con il JSON, senza altro testo."""

        print("🤖 Analisi in corso con Google Gemini 1.5 Pro...")

        # Genera risposta
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Pulisci il JSON dalla risposta (rimuovi eventuali markdown code blocks)
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()

        # Parse JSON
        try:
            metadata = json.loads(response_text)
            return metadata
        except json.JSONDecodeError:
            print("⚠️  Errore nel parsing JSON. Testo ricevuto:")
            print(response_text)
            # Fallback: crea metadati di base
            return {
                "titolo": "Video senza titolo",
                "descrizione": transcript[:300] + "..." if len(transcript) > 300 else transcript,
                "prompt_immagine": "professional video thumbnail, high quality, eye-catching design"
            }

    except ImportError:
        print("❌ Errore: google-generativeai non installato.")
        print("   Installa con: pip install google-generativeai")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Errore durante l'analisi con Gemini: {e}")
        sys.exit(1)


def save_metadata(metadata: Dict[str, str], output_path: str) -> None:
    """
    Salva i metadati in un file TXT.

    :param metadata: Dict con titolo, descrizione e prompt immagine
    :param output_path: Percorso del file di output
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("METADATI VIDEO - Generati con Google Gemini 1.5 Pro\n")
            f.write("=" * 80 + "\n\n")

            f.write("📌 TITOLO\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('titolo', 'N/A') + "\n\n")

            f.write("📝 DESCRIZIONE\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('descrizione', 'N/A') + "\n\n")

            f.write("🎨 PROMPT IMMAGINE DI COPERTINA\n")
            f.write("-" * 80 + "\n")
            f.write("(Usa questo prompt con Stable Diffusion, DALL-E, Midjourney, etc.)\n\n")
            f.write(metadata.get('prompt_immagine', 'N/A') + "\n\n")

            f.write("=" * 80 + "\n")
            f.write("Nota: Genera l'immagine di copertina usando il prompt sopra\n")
            f.write("con un modello AI come:\n")
            f.write("  - Stable Diffusion (locale o online)\n")
            f.write("  - DALL-E 3 (OpenAI)\n")
            f.write("  - Midjourney\n")
            f.write("  - Leonardo.ai\n")
            f.write("=" * 80 + "\n")

        print(f"✅ Metadati salvati in: {output_path}")

    except Exception as e:
        print(f"❌ Errore durante il salvataggio: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Genera metadati video analizzando i sottotitoli con Google Gemini"
    )
    parser.add_argument('transcript_file',
                       help='File di trascrizione (_transcript.txt)')
    parser.add_argument('--api-key',
                       help='Chiave API di Google Gemini (o usa GEMINI_API_KEY env var)')
    parser.add_argument('-o', '--output',
                       help='File di output per i metadati (default: {nome}_metadata.txt)')

    args = parser.parse_args()

    # Verifica API key
    api_key = args.api_key or os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Errore: Chiave API non fornita!")
        print("\nUsa uno di questi metodi:")
        print("  1. Parametro: --api-key YOUR_API_KEY")
        print("  2. Variabile ambiente: export GEMINI_API_KEY=YOUR_API_KEY")
        print("\nOttieni una chiave API gratuita su: https://makersuite.google.com/app/apikey")
        sys.exit(1)

    # Determina percorso di output
    if args.output:
        output_path = args.output
    else:
        # Usa il nome del file di input sostituendo _transcript.txt con _metadata.txt
        input_path = Path(args.transcript_file)
        if input_path.stem.endswith('_transcript'):
            base_name = input_path.stem.replace('_transcript', '')
        else:
            base_name = input_path.stem
        output_path = str(input_path.parent / f"{base_name}_metadata.txt")

    print("\n" + "=" * 80)
    print("Video Metadata Generator - Powered by Google Gemini 1.5 Pro")
    print("=" * 80)
    print(f"📄 Input: {args.transcript_file}")
    print(f"📤 Output: {output_path}")
    print("=" * 80 + "\n")

    # Carica trascrizione
    print("📖 Caricamento trascrizione...")
    transcript = load_transcript(args.transcript_file)
    print(f"✓ Trascrizione caricata: {len(transcript)} caratteri\n")

    # Analizza con Gemini
    metadata = analyze_with_gemini(transcript, api_key)
    print("✓ Analisi completata!\n")

    # Mostra anteprima
    print("📋 Anteprima Metadati:")
    print("-" * 80)
    print(f"Titolo: {metadata.get('titolo', 'N/A')[:70]}...")
    print(f"Descrizione: {metadata.get('descrizione', 'N/A')[:100]}...")
    print(f"Prompt: {metadata.get('prompt_immagine', 'N/A')[:100]}...")
    print("-" * 80 + "\n")

    # Salva metadati
    save_metadata(metadata, output_path)

    print("\n✅ Completato!")
    print(f"\n💡 Prossimi passi:")
    print(f"   1. Apri il file: {output_path}")
    print(f"   2. Copia il 'PROMPT IMMAGINE DI COPERTINA'")
    print(f"   3. Genera l'immagine con un AI image generator")
    print(f"   4. Usa titolo e descrizione per pubblicare il video\n")


if __name__ == '__main__':
    main()
