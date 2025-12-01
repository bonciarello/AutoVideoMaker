#!/usr/bin/env python3
"""
Flusso 6: Generazione Metadati AI
Genera metadati video e thumbnail usando Google Gemini AI.
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional


def analyze_with_gemini(transcript: str, api_key: str) -> Optional[Dict[str, str]]:
    """
    Analizza la trascrizione usando Google Gemini API.

    :param transcript: Testo della trascrizione
    :param api_key: Chiave API di Google Gemini
    :return: Dizionario con metadati generati o None se errore
    """
    try:
        import google.generativeai as genai

        # Configura Gemini
        genai.configure(api_key=api_key)

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
            print("Errore nel parsing JSON. Testo ricevuto:")
            print(response_text)
            # Fallback
            return {
                "titolo": "Video senza titolo",
                "descrizione": transcript[:300] + "..." if len(transcript) > 300 else transcript,
                "tags": "",
                "prompt_immagine": "professional video thumbnail, high quality"
            }

    except ImportError:
        print("google-generativeai non installato. Salta generazione metadati.")
        return None
    except Exception as e:
        error_message = str(e)
        if "quota" in error_message.lower() or "rate limit" in error_message.lower():
            print(f"Errore di quota API superata!")
            print(f"   Stai usando {model_name}. Attendi qualche minuto o passa a gemini-1.5-flash.")
        else:
            print(f"Errore durante l'analisi con Gemini: {e}")
        return None


def generate_thumbnail_with_gemini(image_prompt: str,
                                   api_key: str,
                                   output_path: str,
                                   personal_image_path: str = "personal_image.png") -> bool:
    """
    Genera un'immagine di copertina YouTube usando Gemini con generazione immagini.

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

        # Verifica immagine personale
        if os.path.exists(personal_image_path):
            with open(personal_image_path, 'rb') as f:
                personal_image_bytes = f.read()
            personal_image_part = types.Part.from_bytes(data=personal_image_bytes, mime_type='image/png')
        else:
            personal_image_part = None

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

        # Salva il prompt completo in un file TXT
        prompt_file_path = output_path.replace('thumbnail.png', 'prompt.txt')
        try:
            with open(prompt_file_path, 'w', encoding='utf-8') as f:
                f.write(full_prompt)
            print(f"File prompt thumbnail generato!")
        except Exception as e:
            print(f"Errore salvataggio prompt: {e}")

        # Client con timeout standard
        client = genai.Client(api_key=api_key)

        # Contenuto
        contents = [full_prompt]
        if personal_image_part:
            contents.append(personal_image_part)

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
                        pil_image = pil_image.resize((1920, 1080), Image.Resampling.LANCZOS)

                    # Salva
                    pil_image.save(output_path, 'PNG', quality=95)
                    print(f"File thumbnail generato!")
                    return True

            return False
        else:
            return False

    except Exception as e:
        print(f"Errore generazione thumbnail: {e}")
        print(f"   Tipo: {type(e).__name__}")
        return False


def save_metadata(metadata: Dict[str, str], output_path: str) -> None:
    """
    Salva i metadati in un file TXT.

    :param metadata: Dizionario con i metadati
    :param output_path: Percorso del file di output
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("METADATI VIDEO\n")
            f.write("=" * 80 + "\n\n")

            f.write("TITOLO\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('titolo', 'N/A') + "\n\n")

            f.write("DESCRIZIONE\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('descrizione', 'N/A') + "\n\n")

            f.write("TAGS\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('tags', 'N/A') + "\n\n")

            f.write("PROMPT IMMAGINE\n")
            f.write("-" * 80 + "\n")
            f.write(metadata.get('prompt_immagine', 'N/A') + "\n\n")

        print(f"File metadati generato!")

    except Exception as e:
        print(f"Errore durante il salvataggio metadati: {e}")


def generate_video_metadata(transcript_path: str,
                           output_folder: str,
                           api_key: Optional[str] = None,
                           personal_image_path: Optional[str] = None) -> None:
    """
    Genera metadati video analizzando la trascrizione con Google Gemini.

    :param transcript_path: Percorso del file di trascrizione
    :param output_folder: Cartella dove salvare i metadati
    :param api_key: Chiave API Gemini (opzionale, usa .env se non specificata)
    :param personal_image_path: Percorso immagine personale (opzionale)
    """
    from utils import log_phase

    # Carica API key da .env se non specificata
    if not api_key:
        api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("Chiave API Gemini non trovata. Salta generazione metadati.")
        print("   Aggiungi GEMINI_API_KEY al file .env per abilitare questa funzionalità.")
        return

    # Carica trascrizione
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = f.read().strip()
    except Exception as e:
        print(f"Errore lettura trascrizione: {e}")
        return

    log_phase("Generazione metadati AI con Gemini")

    # Analizza con Gemini
    metadata = analyze_with_gemini(transcript, api_key)

    if not metadata:
        return

    # Salva metadati
    metadata_path = os.path.join(output_folder, "metadata.txt")
    save_metadata(metadata, metadata_path)

    # Genera thumbnail YouTube con Gemini (se disponibile)
    if metadata.get('prompt_immagine'):
        # Determina percorso dell'immagine personale
        if personal_image_path is None:
            project_root = Path(__file__).parent
            personal_image_path = str(project_root / "personal_image.png")

        # Determina percorso output thumbnail
        thumbnail_path = os.path.join(output_folder, "thumbnail.png")

        generate_thumbnail_with_gemini(
            image_prompt=metadata['prompt_immagine'],
            api_key=api_key,
            output_path=thumbnail_path,
            personal_image_path=personal_image_path
        )


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Uso: python 6_metadata_generation.py <transcript_path> <output_folder> [api_key]")
        sys.exit(1)

    transcript = sys.argv[1]
    output = sys.argv[2]
    key = sys.argv[3] if len(sys.argv) > 3 else None

    generate_video_metadata(transcript, output, key)
