#!/usr/bin/env python3
"""
Flusso 6: Generazione Metadati AI
Genera metadati testuali del video con Claude Opus 5 (Anthropic)
e thumbnail YouTube con GPT Images 2 (OpenAI).

Chiavi API richieste nel file .env:
- ANTHROPIC_API_KEY: per titolo, descrizione, tags e prompt immagine
- OPENAI_API_KEY: per la generazione della thumbnail (opzionale)
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional

# Modello Anthropic per i metadati testuali (condiviso con la pulizia take)
from utils import CLAUDE_MODEL

# Modello OpenAI per la generazione delle immagini di copertina
OPENAI_IMAGE_MODEL = 'gpt-image-2'

# Risoluzione finale della thumbnail YouTube
THUMBNAIL_SIZE = (1920, 1080)


def analyze_with_claude(transcript: str, api_key: str) -> Optional[Dict[str, str]]:
    """
    Analizza la trascrizione usando Claude Opus 5 (Anthropic API).

    :param transcript: Testo della trascrizione
    :param api_key: Chiave API Anthropic
    :return: Dizionario con metadati generati o None se errore
    """
    try:
        import anthropic
    except ImportError:
        print("anthropic non installato. Salta generazione metadati.")
        print("   Installa con: pip install anthropic")
        return None

    # Prompt per l'analisi
    prompt = f"""Analizza la seguente trascrizione di un video e genera:

1. **TITOLO**: Un titolo accattivante e SEO-friendly per il video (max 70 caratteri)
2. **DESCRIZIONE**: Una descrizione dettagliata del contenuto del video (200-300 parole) scritta in prima persona
3. **TAGS**: Una lista di 10-15 tag rilevanti per il video, separati da virgola. I tag devono essere specifici, SEO-friendly e rappresentare i concetti chiave trattati nel video.
4. **PROMPT_IMMAGINE**: Un prompt dettagliato in inglese per generare un'immagine di copertina usando un modello AI text-to-image. Il prompt deve descrivere l'argomento/tema trattato nel video (non il contesto di realizzazione), essere descrittivo, specifico e adatto a un modello di generazione immagini. La scena descritta deve essere realistica e fotografabile (persone, oggetti e ambienti reali), non illustrativa o stilizzata.

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

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        # Il modello può restituire più blocchi (es. ThinkingBlock + TextBlock):
        # concatena solo i blocchi di testo
        response_text = "".join(
            block.text for block in message.content
            if getattr(block, "type", None) == "text"
        ).strip()

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

    except Exception as e:
        error_message = str(e).lower()
        if "quota" in error_message or "rate" in error_message or "credit" in error_message:
            print("Errore di quota/limite API Anthropic superato!")
            print(f"   Stai usando {CLAUDE_MODEL}. Attendi qualche minuto o verifica il tuo piano.")
        else:
            print(f"Errore durante l'analisi con Claude: {e}")
        return None


def generate_thumbnail_with_openai(image_prompt: str,
                                   api_key: str,
                                   output_path: str,
                                   personal_image_path: str = "personal_image.png") -> bool:
    """
    Genera un'immagine di copertina YouTube usando GPT Images 2 (OpenAI).

    :param image_prompt: Prompt per la generazione dell'immagine
    :param api_key: Chiave API OpenAI
    :param output_path: Percorso dove salvare l'immagine generata
    :param personal_image_path: Percorso dell'immagine personale da includere
    :return: True se generata con successo, False altrimenti
    """
    try:
        from openai import OpenAI
        from PIL import Image
        import base64
        import io
    except ImportError:
        print("openai o pillow non installato. Salta generazione thumbnail.")
        print("   Installa con: pip install openai pillow")
        return False

    # Crea la cartella di output se non esiste
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    has_personal_image = os.path.exists(personal_image_path)

    # Stile comune: FOTOREALISTICO (non illustrazione, non render 3D)
    photorealistic_style = (
        "PHOTOREALISTIC style: the image must look like a real professional photograph, "
        "shot with a high-end camera. Realistic materials, natural skin, real-world lighting, "
        "depth of field, sharp photographic details. Absolutely NOT an illustration, NOT a 3D render, "
        "NOT a cartoon or CGI look."
    )

    # Costruisci prompt dettagliato per thumbnail YouTube
    if has_personal_image:
        full_prompt = f"""Create a professional YouTube thumbnail with these specifications:

LAYOUT: 16:9 aspect ratio (1920x1080), split composition with person on one side and content on the other

PERSON STYLING: Integrate the person from the provided image seamlessly into the scene. IMPORTANT: Modify the person's facial expression to show excitement, surprise, or strong emotion related to the video topic (amazed, shocked, enthusiastic, etc.). The person should appear natural and engaging, with proper lighting that matches the overall aesthetic. Position them prominently but balanced with the content side.

CONTENT SIDE: {image_prompt}. Use ICONS and visual symbols instead of text. NO text, NO titles, NO words - only visual elements and icons that represent the content.

OVERALL STYLE: {photorealistic_style} Professional YouTube thumbnail quality, vibrant colors, high contrast, dramatic lighting, balanced composition, eye-catching yet cohesive design. Absolutely NO text or written words anywhere in the image."""
    else:
        full_prompt = f"""Create a professional YouTube thumbnail with these specifications:

LAYOUT: 16:9 aspect ratio (1920x1080)

CONTENT: {image_prompt}. Use ICONS and visual symbols instead of text. NO text, NO titles, NO words - only visual elements and icons that represent the content.

OVERALL STYLE: {photorealistic_style} Professional YouTube thumbnail quality, vibrant colors, high contrast, dramatic lighting, balanced composition, eye-catching design. Absolutely NO text or written words anywhere in the image."""

    # Salva il prompt completo in un file TXT
    prompt_file_path = output_path.replace('thumbnail.png', 'prompt.txt')
    try:
        with open(prompt_file_path, 'w', encoding='utf-8') as f:
            f.write(full_prompt)
        print("File prompt thumbnail generato!")
    except Exception as e:
        print(f"Errore salvataggio prompt: {e}")

    try:
        client = OpenAI(api_key=api_key)

        def _call_api(size: str):
            """Chiama l'API immagini con la risoluzione richiesta."""
            if has_personal_image:
                # Con immagine personale: usa images.edit per integrarla nella thumbnail
                with open(personal_image_path, 'rb') as image_file:
                    return client.images.edit(
                        model=OPENAI_IMAGE_MODEL,
                        image=image_file,
                        prompt=full_prompt,
                        size=size
                    )
            # Senza immagine personale: generazione da zero
            return client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=full_prompt,
                size=size,
                quality="high"
            )

        # Prova la risoluzione nativa 1920x1080 (16:9 esatto);
        # se il modello non la supporta, fallback a 1536x1024 + crop 16:9
        try:
            response = _call_api("1920x1080")
        except Exception as e:
            if "size" in str(e).lower():
                print(f"   Risoluzione 1920x1080 non supportata, uso 1536x1024 + crop 16:9")
                response = _call_api("1536x1024")
            else:
                raise

        # Estrai immagine (i modelli gpt-image ritornano sempre base64)
        image_b64 = response.data[0].b64_json
        image_data = base64.b64decode(image_b64)
        pil_image = Image.open(io.BytesIO(image_data))

        # Porta l'immagine a 1920x1080 esatti: prima crop centrale al rapporto
        # 16:9 (evita distorsioni), poi resize se necessario
        target_size = THUMBNAIL_SIZE
        if pil_image.size != target_size:
            w, h = pil_image.size
            target_ratio = target_size[0] / target_size[1]
            current_ratio = w / h

            if current_ratio > target_ratio:
                # Troppo larga: crop laterale
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                pil_image = pil_image.crop((left, 0, left + new_w, h))
            elif current_ratio < target_ratio:
                # Troppo alta: crop sopra/sotto
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                pil_image = pil_image.crop((0, top, w, top + new_h))

            if pil_image.size != target_size:
                pil_image = pil_image.resize(target_size, Image.Resampling.LANCZOS)

        # Salva
        pil_image.save(output_path, 'PNG')
        print(f"File thumbnail generato! ({pil_image.size[0]}x{pil_image.size[1]})")
        return True

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

        print("File metadati generato!")

    except Exception as e:
        print(f"Errore durante il salvataggio metadati: {e}")


def generate_video_metadata(transcript_path: str,
                            output_folder: str,
                            anthropic_api_key: Optional[str] = None,
                            openai_api_key: Optional[str] = None,
                            personal_image_path: Optional[str] = None) -> None:
    """
    Genera metadati video analizzando la trascrizione con Claude Opus 5
    e la thumbnail con GPT Images 2.

    :param transcript_path: Percorso del file di trascrizione
    :param output_folder: Cartella dove salvare i metadati
    :param anthropic_api_key: Chiave API Anthropic (opzionale, usa .env se non specificata)
    :param openai_api_key: Chiave API OpenAI (opzionale, usa .env se non specificata)
    :param personal_image_path: Percorso immagine personale (opzionale)
    """
    from utils import log_phase

    # Carica .env per ottenere le chiavi API
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv non disponibile, usa variabili d'ambiente del sistema

    # Carica API keys da .env se non specificate
    if not anthropic_api_key:
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not openai_api_key:
        openai_api_key = os.getenv('OPENAI_API_KEY')

    if not anthropic_api_key:
        print("Chiave API Anthropic non trovata. Salta generazione metadati.")
        print("   Aggiungi ANTHROPIC_API_KEY al file .env per abilitare questa funzionalità.")
        return

    # Carica trascrizione
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = f.read().strip()
    except Exception as e:
        print(f"Errore lettura trascrizione: {e}")
        return

    log_phase("Generazione metadati AI con Claude")

    # Analizza con Claude Opus 5
    metadata = analyze_with_claude(transcript, anthropic_api_key)

    if not metadata:
        return

    # Salva metadati
    metadata_path = os.path.join(output_folder, "metadata.txt")
    save_metadata(metadata, metadata_path)

    # Genera thumbnail YouTube con GPT Images 2 (se disponibile)
    if metadata.get('prompt_immagine'):
        if not openai_api_key:
            print("Chiave API OpenAI non trovata. Salta generazione thumbnail.")
            print("   Aggiungi OPENAI_API_KEY al file .env per abilitare questa funzionalità.")
            return

        # Determina percorso dell'immagine personale
        if personal_image_path is None:
            # Il file personal_image.png è nella root del progetto, non in src/
            project_root = Path(__file__).parent.parent
            personal_image_path = str(project_root / "personal_image.png")

        # Determina percorso output thumbnail
        thumbnail_path = os.path.join(output_folder, "thumbnail.png")

        generate_thumbnail_with_openai(
            image_prompt=metadata['prompt_immagine'],
            api_key=openai_api_key,
            output_path=thumbnail_path,
            personal_image_path=personal_image_path
        )


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Uso: python metadata_generation.py <transcript_path> <output_folder> [anthropic_api_key] [openai_api_key]")
        sys.exit(1)

    transcript = sys.argv[1]
    output = sys.argv[2]
    anthropic_key = sys.argv[3] if len(sys.argv) > 3 else None
    openai_key = sys.argv[4] if len(sys.argv) > 4 else None

    generate_video_metadata(transcript, output, anthropic_key, openai_key)
