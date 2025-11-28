#!/usr/bin/env python3
"""
Video Metadata Generator
Analizza i sottotitoli usando Google Gemini API e genera metadati per il video.
Supporta file .env per la configurazione.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Optional

# Tenta di importare dotenv per caricare il file .env
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

def load_transcript(transcript_path: str) -> str:
    """
    Carica la trascrizione dal file TXT.
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
    """
    try:
        import google.generativeai as genai

        # Configura Gemini
        genai.configure(api_key=api_key)
        
        # USARE MODELLO REALE: gemini-3 non esiste ancora, uso gemini-1.5-pro (il più potente attuale)
        model_name = 'gemini-3-pro-preview'
        model = genai.GenerativeModel(model_name)

        # Prompt per l'analisi
        prompt = f"""Analizza la seguente trascrizione di un video e genera:

1. **TITOLO**: Un titolo accattivante e SEO-friendly per il video (max 70 caratteri)
2. **DESCRIZIONE**: Una descrizione dettagliata del contenuto del video (200-300 parole) scritta in prima persona
3. **TAGS**: Una lista di 10-15 tag rilevanti per il video, separati da virgola. I tag devono essere specifici, SEO-friendly e rappresentare i concetti chiave trattati nel video.
4. **PROMPT_IMMAGINE**: Un prompt dettagliato in inglese per generare un'immagine di copertina usando un modello AI text-to-image. Il prompt deve descrivere l'argomento/tema trattato nel video (non il contesto di realizzazione), essere descrittivo, specifico e adatto a Stable Diffusion / DALL-E.

Formato della risposta (JSON):
{{
  "titolo": "...",
  "descrizione": "...",
  "tags": "tag1, tag2, tag3, ...",
  "prompt_immagine": "..."
}}

TRASCRIZIONE:
{transcript}

Rispondi SOLO con il JSON, senza altro testo."""

        print(f"🤖 Analisi in corso con Google Gemini ({model_name})...")

        # Genera risposta
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Pulisci il JSON dalla risposta
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
            # Fallback
            return {
                "titolo": "Video senza titolo",
                "descrizione": transcript[:300] + "..." if len(transcript) > 300 else transcript,
                "prompt_immagine": "professional video thumbnail, high quality"
            }

    except ImportError:
        print("❌ Errore: google-generativeai non installato.")
        sys.exit(1)
    except Exception as e:
        error_message = str(e)
        if "quota" in error_message.lower() or "rate limit" in error_message.lower():
            print(f"❌ Errore di quota API superata!")
            print(f"   Stai usando {model_name}. Attendi qualche minuto o passa a gemini-1.5-flash.")
        else:
            print(f"❌ Errore durante l'analisi con Gemini: {e}")
        sys.exit(1)


def generate_thumbnail_with_gemini(image_prompt: str, api_key: str, output_path: str, personal_image_path: str = "personal_image.png") -> bool:
    """
    Genera un'immagine di copertina YouTube usando Gemini 3 Pro con generazione immagini.

    :param image_prompt: Prompt per la generazione dell'immagine
    :param api_key: Chiave API di Google Gemini
    :param output_path: Percorso dove salvare l'immagine generata
    :param personal_image_path: Percorso dell'immagine personale da includere
    :return: True se generata con successo, False altrimenti
    """
    try:
        from google import genai
        from google.genai import types
        from PIL import Image
        import io

        print(f"🎨 Generando thumbnail YouTube con Gemini...")
        print(f"   Dimensioni: 1920x1080")

        # Verifica immagine personale
        if os.path.exists(personal_image_path):
            with open(personal_image_path, 'rb') as f:
                personal_image_bytes = f.read()
            personal_image_part = types.Part.from_bytes(data=personal_image_bytes, mime_type='image/png')
            print(f"   ✓ Immagine caricata: {personal_image_path}")
        else:
            personal_image_part = None
            print(f"   ⚠️  Immagine non trovata: {personal_image_path}")

        # Costruisci prompt dettagliato per thumbnail YouTube
        if personal_image_part:
            full_prompt = f"""Create a professional YouTube thumbnail with these specifications:

LAYOUT: 16:9 aspect ratio (1920x1080), split composition with person on one side and content on the other

PERSON STYLING: Integrate the person from the provided image seamlessly into the scene. The person should appear natural and engaging, with proper lighting that matches the overall aesthetic. Position them prominently but balanced with the content side.

CONTENT SIDE: {image_prompt}

OVERALL STYLE: Professional YouTube thumbnail quality, vibrant colors, high contrast, dramatic lighting, balanced composition, eye-catching yet cohesive design"""
        else:
            full_prompt = f"""Create a professional YouTube thumbnail with these specifications:

LAYOUT: 16:9 aspect ratio (1920x1080)

CONTENT: {image_prompt}

OVERALL STYLE: Professional YouTube thumbnail quality, vibrant colors, high contrast, dramatic lighting, balanced composition, eye-catching design"""

        print(f"   📝 Prompt: {full_prompt[:80]}...")

        # Salva il prompt completo in un file TXT
        prompt_file_path = output_path.replace('thumbnail.png', 'prompt.txt')
        try:
            with open(prompt_file_path, 'w', encoding='utf-8') as f:
                f.write(full_prompt)
            print(f"    [OK] {prompt_file_path}")
        except Exception as e:
            print(f"   ⚠️  Errore salvataggio prompt: {e}")

        # Client con timeout standard
        client = genai.Client(api_key=api_key)

        # Contenuto
        contents = [full_prompt]
        if personal_image_part:
            contents.append(personal_image_part)

        print(f"   ⏳ Generazione...")

        # Genera
        response = client.models.generate_content(
            model='models/gemini-3-pro-image-preview',
            contents=contents,
            config=types.GenerateContentConfig(
                image_config=types.ImageConfig(
                    aspect_ratio='16:9',
                    image_size='4K'
                )
            )
        )

        # Estrai immagine
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]

            for part in candidate.content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    image_data = part.inline_data.data
                    pil_image = Image.open(io.BytesIO(image_data))

                    # Ridimensiona
                    if pil_image.size != (1920, 1080):
                        print(f"   🔧 Ridimensiona: {pil_image.size} → (1920, 1080)")
                        pil_image = pil_image.resize((1920, 1080), Image.Resampling.LANCZOS)

                    # Salva
                    pil_image.save(output_path, 'PNG', quality=95)
                    print(f"    [OK] {output_path}")
                    return True

            print("⚠️  Nessuna immagine nella risposta")
            return False
        else:
            print("⚠️  Nessun candidato")
            return False

    except Exception as e:
        print(f"⚠️  Errore: {e}")
        print(f"   Tipo: {type(e).__name__}")
        return False


def save_metadata(metadata: Dict[str, str], output_path: str) -> None:
    """
    Salva i metadati in un file TXT.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("METADATI VIDEO\n")
            f.write("=" * 80 + "\n\n")

            f.write("📌 TITOLO\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('titolo', 'N/A') + "\n\n")

            f.write("📝 DESCRIZIONE\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('descrizione', 'N/A') + "\n\n")

            f.write("🏷️  TAGS\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('tags', 'N/A') + "\n\n")

            f.write("🎨 PROMPT IMMAGINE\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('prompt_immagine', 'N/A') + "\n\n")
        
        print(f"    [OK] {output_path}")

    except Exception as e:
        print(f"❌ Errore durante il salvataggio: {e}")
        sys.exit(1)


def main():
    # --- CARICAMENTO .ENV ---
    if DOTENV_AVAILABLE:
        load_dotenv() # Cerca il file .env nella cartella corrente
    else:
        # Avviso non bloccante, magari l'utente passa la chiave via args
        pass 
    # ------------------------

    parser = argparse.ArgumentParser(
        description="Genera metadati video analizzando i sottotitoli con Google Gemini"
    )
    parser.add_argument('transcript_file',
                       help='File di trascrizione (_transcript.txt)')
    parser.add_argument('--api-key',
                       help='Chiave API (opzionale se presente nel file .env)')
    parser.add_argument('-o', '--output',
                       help='File di output per i metadati')

    args = parser.parse_args()

    # Logica di recupero chiave:
    # 1. Prima controlla se è passata come argomento --api-key
    # 2. Se no, controlla la variabile d'ambiente (caricata da .env o dal sistema)
    api_key = args.api_key or os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("❌ Errore: Chiave API non trovata!")
        print("\nAssicurati di avere un file .env con:")
        print("GEMINI_API_KEY=AIzaSy...")
        print("\nOppure installa python-dotenv: pip install python-dotenv")
        sys.exit(1)

    # Determina percorso di output
    if args.output:
        output_path = args.output
    else:
        input_path = Path(args.transcript_file)
        output_path = str(input_path.parent / "metadata.txt")

    print("\n" + "=" * 80)
    print("Video Metadata Generator")
    print("=" * 80)
    print(f"📄 Input: {args.transcript_file}")
    
    # Carica trascrizione
    transcript = load_transcript(args.transcript_file)
    print(f"✓ Trascrizione caricata: {len(transcript)} caratteri")

    # Analizza con Gemini
    metadata = analyze_with_gemini(transcript, api_key)
    print("✓ Analisi completata!\n")

    # Mostra anteprima
    print(f"Titolo generato: {metadata.get('titolo', 'N/A')}")

    # Salva metadati
    save_metadata(metadata, output_path)

    # Genera thumbnail YouTube con Gemini (se disponibile)
    input_path = Path(args.transcript_file)
    output_dir = input_path.parent

    # Determina percorso dell'immagine personale (nella root del progetto)
    project_root = Path(__file__).parent
    personal_image_path = project_root / "personal_image.png"

    # Determina percorso output thumbnail
    thumbnail_path = str(output_dir / "thumbnail.png")

    if metadata.get('prompt_immagine'):
        print("\n" + "=" * 80)
        print("Generazione Thumbnail YouTube")
        print("=" * 80)

        success = generate_thumbnail_with_gemini(
            image_prompt=metadata['prompt_immagine'],
            api_key=api_key,
            output_path=thumbnail_path,
            personal_image_path=str(personal_image_path)
        )

        if not success:
            print(f"\n⚠️  Thumbnail non generata (feature sperimentale)")

if __name__ == '__main__':
    main()