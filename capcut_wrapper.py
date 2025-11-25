"""
Wrapper semplificato per creare progetti CapCut tagliando fisicamente i video
"""

import os
import sys
import shutil
import subprocess
import json
import time
from pathlib import Path
from typing import List, Tuple, Dict
from datetime import datetime
import uuid


class CapCutProjectBuilder:
    """Builder per creare progetti CapCut con video pre-tagliati"""

    def __init__(self, width: int = 1920, height: int = 1080):
        """
        Inizializza il builder del progetto CapCut

        :param width: Larghezza del canvas
        :param height: Altezza del canvas
        """
        self.width = width
        self.height = height
        self.segment_files = []  # Lista di file video tagliati
        self.project_duration = 0  # Durata totale in microsecondi

    def add_video_segments(self, video_path: str, segments: List[Tuple[float, float]],
                          video_info: Dict, temp_dir: str) -> None:
        """
        Crea segmenti video separati usando filtri FFmpeg (identico al processing video export)

        :param video_path: Percorso del video originale
        :param segments: Lista di tuple (start, end) in secondi dei segmenti da mantenere
        :param video_info: Informazioni sul video da ffprobe
        :param temp_dir: Directory temporanea per salvare i segmenti
        """
        # Rileva codec originali
        video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'audio'), None)

        video_codec = video_stream.get('codec_name', 'libx264') if video_stream else 'libx264'
        audio_codec = audio_stream.get('codec_name', 'aac') if audio_stream else 'aac'
        audio_bitrate = audio_stream.get('bit_rate', '192000') if audio_stream else '192000'
        pixel_format = video_stream.get('pix_fmt', 'yuv420p') if video_stream else 'yuv420p'

        # Converti audio_bitrate in formato kbps
        try:
            audio_bitrate_k = f"{int(audio_bitrate) // 1000}k"
        except (ValueError, TypeError):
            audio_bitrate_k = '192k'

        # Mappa codec FFmpeg
        codec_map = {
            'h264': 'libx264',
            'h265': 'libx265',
            'hevc': 'libx265',
            'vp8': 'libvpx',
            'vp9': 'libvpx-vp9',
            'mpeg4': 'mpeg4',
            'mjpeg': 'mjpeg'
        }
        video_encoder = codec_map.get(video_codec, video_codec)

        audio_codec_map = {
            'mp3': 'libmp3lame',
            'vorbis': 'libvorbis',
            'opus': 'libopus'
        }
        audio_encoder = audio_codec_map.get(audio_codec, audio_codec)

        # Crea directory per i segmenti
        segments_dir = os.path.join(temp_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)

        # Barra di caricamento
        total_segments = len(segments)
        start_time = time.time()

        print(f"\n📹 Creando {total_segments} segmenti CapCut...")

        # Processa ogni segmento separatamente usando filtri FFmpeg
        for i, (start, end) in enumerate(segments):
            duration = end - start

            # Nome file segmento
            segment_filename = f"segment_{i:03d}.mp4"
            segment_path = os.path.join(segments_dir, segment_filename)

            # Usa filtri trim/atrim (identico al video export, ma per un segmento alla volta)
            filter_complex = f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v];[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a]"

            # Costruisci comando FFmpeg
            cmd = [
                'ffmpeg', '-i', video_path,
                '-filter_complex', filter_complex,
                '-map', '[v]', '-map', '[a]',
                '-c:v', video_encoder,
                '-pix_fmt', pixel_format,
                '-c:a', audio_encoder,
                '-b:a', audio_bitrate_k,
                '-y', segment_path
            ]

            # Per h264/h265, usa crf
            if video_encoder in ['libx264', 'libx265']:
                cmd.insert(cmd.index('-pix_fmt'), '-crf')
                cmd.insert(cmd.index('-pix_fmt'), '18')
                cmd.insert(cmd.index('-pix_fmt'), '-preset')
                cmd.insert(cmd.index('-pix_fmt'), 'medium')

            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )

                # Salva info segmento
                self.segment_files.append({
                    'path': segment_path,
                    'filename': segment_filename,
                    'start': start,
                    'end': end,
                    'duration': duration
                })

                self.project_duration += int(duration * 1000000)

            except subprocess.CalledProcessError:
                # Fallback a codec standard (silenzioso)
                cmd_fallback = [
                    'ffmpeg', '-i', video_path,
                    '-filter_complex', filter_complex,
                    '-map', '[v]', '-map', '[a]',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                    '-c:a', 'aac', '-b:a', audio_bitrate_k,
                    '-y', segment_path
                ]
                subprocess.run(cmd_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                self.segment_files.append({
                    'path': segment_path,
                    'filename': segment_filename,
                    'start': start,
                    'end': end,
                    'duration': duration
                })
                self.project_duration += int(duration * 1000000)

            # Calcola progresso e tempo rimanente
            progress = ((i + 1) / total_segments) * 100
            elapsed_time = time.time() - start_time
            avg_time_per_segment = elapsed_time / (i + 1)
            remaining_segments = total_segments - (i + 1)
            eta_seconds = avg_time_per_segment * remaining_segments

            # Formatta ETA
            if eta_seconds < 60:
                eta_str = f"{int(eta_seconds)}s"
            else:
                eta_min = int(eta_seconds // 60)
                eta_sec = int(eta_seconds % 60)
                eta_str = f"{eta_min}m {eta_sec}s"

            # Barra di progresso
            bar_length = 30
            filled_length = int(bar_length * (i + 1) / total_segments)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)

            # Stampa barra (sovrascrive la riga)
            print(f"\r  [{bar}] {progress:.1f}% | {i+1}/{total_segments} | ETA: {eta_str}  ", end='', flush=True)

        print()  # Nuova riga finale
        print(f"✓ {len(self.segment_files)} segmenti creati con successo")

    def save_to_capcut_folder(self, project_name: str,
                             capcut_dir: str = None,
                             template_project: str = None) -> str:
        """
        Salva il progetto CapCut con i segmenti video pre-tagliati

        :param project_name: Nome del progetto
        :param capcut_dir: Percorso base dei progetti CapCut (opzionale)
        :param template_project: Nome di un progetto esistente da clonare (opzionale)
        :return: Percorso completo del progetto creato
        """
        print(f"\n📁 Creando progetto CapCut...")

        # Usa il percorso default di CapCut se non specificato
        if capcut_dir is None:
            capcut_dir = str(Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft")

        # Crea directory se non esiste
        os.makedirs(capcut_dir, exist_ok=True)

        # Trova un progetto esistente da clonare se non specificato
        if template_project is None:
            # Cerca progetti esistenti
            existing_projects = [d for d in os.listdir(capcut_dir)
                               if os.path.isdir(os.path.join(capcut_dir, d))
                               and not d.startswith('.')]
            if existing_projects:
                # Usa il progetto più recente
                template_project = max(existing_projects,
                                     key=lambda d: os.path.getmtime(os.path.join(capcut_dir, d)))
                print(f"  📋 Usando progetto template: {template_project}")

        # Crea nome univoco se già esiste
        base_project_name = project_name
        counter = 1
        while os.path.exists(os.path.join(capcut_dir, project_name)):
            project_name = f"{base_project_name}_{counter}"
            counter += 1

        project_path = os.path.join(capcut_dir, project_name)

        # Clona il progetto template se esiste
        if template_project:
            template_path = os.path.join(capcut_dir, template_project)
            if os.path.exists(template_path):
                print(f"  🔄 Clonando progetto esistente...")
                shutil.copytree(template_path, project_path)

                # Rimuovi i video vecchi dal progetto
                for item in os.listdir(project_path):
                    item_path = os.path.join(project_path, item)
                    if item.endswith(('.mp4', '.mov', '.avi', '.mkv')) and os.path.isfile(item_path):
                        os.remove(item_path)
            else:
                print(f"  ⚠️  Progetto template non trovato, creo struttura base...")
                os.makedirs(project_path, exist_ok=True)
                self._create_minimal_structure(project_path)
        else:
            # Prova con il template della libreria
            os.makedirs(project_path, exist_ok=True)
            template_dir = Path(__file__).parent / "capcut_api_lib" / "template"
            if template_dir.exists():
                print("  📋 Copiando template CapCut dalla libreria...")
                for item in template_dir.iterdir():
                    if item.name not in ['draft_info.json', 'draft_meta_info.json', 'draft_info.json.bak']:
                        dest = os.path.join(project_path, item.name)
                        if item.is_file():
                            shutil.copy2(item, dest)
                        elif item.is_dir():
                            if not os.path.exists(dest):
                                shutil.copytree(item, dest)
            else:
                # Crea struttura minima
                self._create_minimal_structure(project_path)

        # Copia i segmenti video nella cartella del progetto
        print("  📦 Copiando segmenti video nel progetto...")
        for segment_info in self.segment_files:
            dest_path = os.path.join(project_path, segment_info['filename'])
            shutil.copy2(segment_info['path'], dest_path)
            segment_info['project_path'] = dest_path

        # Se abbiamo clonato un progetto, modifica i JSON esistenti invece di rigenerarli
        draft_info_path = os.path.join(project_path, "draft_info.json")
        draft_meta_path = os.path.join(project_path, "draft_meta_info.json")

        if template_project and os.path.exists(draft_info_path):
            print("  🔧 Modificando JSON del progetto template...")
            self._modify_existing_draft_info(draft_info_path)
            self._modify_existing_meta_info(draft_meta_path, project_name)
        else:
            # Crea draft_info.json con i segmenti
            self._create_draft_info(project_path)
            # Crea draft_meta_info.json
            self._create_meta_info(project_path, project_name)

        print(f"✓ Progetto CapCut creato: {project_path}")
        print(f"  Segmenti video: {len(self.segment_files)}")
        print(f"  Durata totale: {self.project_duration / 1000000:.2f}s")

        return project_path

    def _modify_existing_draft_info(self, draft_info_path: str) -> None:
        """Modifica il draft_info.json esistente sostituendo solo i video"""
        # Leggi il JSON esistente
        with open(draft_info_path, 'r', encoding='utf-8') as f:
            draft_info = json.load(f)

        # Crea i materiali e i segmenti per i nuovi video
        materials_videos = []
        segments = []
        current_time = 0

        for i, seg_info in enumerate(self.segment_files):
            segment_id = str(uuid.uuid4()).replace('-', '')
            material_id = str(uuid.uuid4()).replace('-', '').upper()
            duration_us = int(seg_info['duration'] * 1000000)

            # Materiale video
            material = {
                "id": material_id,
                "type": "video",
                "path": os.path.abspath(seg_info['project_path']),
                "material_name": seg_info['filename'],
                "duration": duration_us,
                "width": self.width,
                "height": self.height,
                "metetype": "local"
            }
            materials_videos.append(material)

            # Segmento video
            segment = {
                "id": segment_id,
                "material_id": material_id,
                "target_timerange": {
                    "start": current_time,
                    "duration": duration_us
                },
                "source_timerange": {
                    "start": 0,
                    "duration": duration_us
                },
                "speed": 1.0,
                "volume": 1.0,
                "enable_adjust": True,
                "enable_color_correct_adjust": False,
                "enable_color_curves": True,
                "enable_color_match_adjust": False,
                "enable_color_wheels": True,
                "enable_lut": True,
                "enable_smart_color_adjust": False,
                "reverse": False,
                "visible": True,
                "clip": {
                    "alpha": 1.0,
                    "flip": {"horizontal": False, "vertical": False},
                    "rotation": 0.0,
                    "scale": {"x": 1.0, "y": 1.0},
                    "transform": {"x": 0.0, "y": 0.0}
                },
                "uniform_scale": {"on": True, "value": 1.0},
                "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
                "last_nonzero_volume": 1.0,
                "track_attribute": 0,
                "track_render_index": 0,
                "common_keyframes": [],
                "keyframe_refs": [],
                "extra_material_refs": []
            }
            segments.append(segment)
            current_time += duration_us

        # Modifica solo i campi necessari mantenendo tutto il resto
        draft_info['duration'] = self.project_duration
        draft_info['materials']['videos'] = materials_videos

        # Trova la track video e sostituisci i segmenti
        for track in draft_info.get('tracks', []):
            if track.get('type') == 'video':
                track['segments'] = segments
                break

        # Salva il JSON modificato
        with open(draft_info_path, 'w', encoding='utf-8') as f:
            json.dump(draft_info, f, indent=2, ensure_ascii=False)

    def _modify_existing_meta_info(self, meta_info_path: str, project_name: str) -> None:
        """Modifica il draft_meta_info.json esistente aggiornando solo i materiali"""
        # Leggi il JSON esistente
        with open(meta_info_path, 'r', encoding='utf-8') as f:
            meta_info = json.load(f)

        current_time = int(datetime.now().timestamp())
        current_time_ms = int(datetime.now().timestamp() * 1000000)

        # Crea lista materiali video
        video_materials = []
        for seg_info in self.segment_files:
            video_materials.append({
                "create_time": current_time,
                "duration": int(seg_info['duration'] * 1000000),
                "extra_info": seg_info['filename'],
                "file_Path": os.path.abspath(seg_info['project_path']),
                "height": self.height,
                "width": self.width,
                "id": str(uuid.uuid4()),
                "import_time": current_time,
                "import_time_ms": current_time_ms,
                "item_source": 1,
                "md5": "",
                "metetype": "local",
                "roughcut_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "sub_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "type": "video"
            })

        # Aggiorna solo i campi necessari
        meta_info['draft_name'] = project_name
        meta_info['tm_draft_modified'] = current_time_ms
        meta_info['tm_duration'] = self.project_duration

        # Sostituisci i materiali video (type 0)
        for material_group in meta_info.get('draft_materials', []):
            if material_group.get('type') == 0:
                material_group['value'] = video_materials
                break

        # Salva il JSON modificato
        with open(meta_info_path, 'w', encoding='utf-8') as f:
            json.dump(meta_info, f, indent=2, ensure_ascii=False)

    def _create_draft_info(self, project_path: str) -> None:
        """Crea il file draft_info.json con i segmenti video"""
        draft_id = str(uuid.uuid4()).upper()

        # Crea i materiali e i segmenti
        materials_videos = []
        segments = []
        current_time = 0

        for i, seg_info in enumerate(self.segment_files):
            segment_id = str(uuid.uuid4()).replace('-', '')
            material_id = str(uuid.uuid4()).replace('-', '').upper()
            duration_us = int(seg_info['duration'] * 1000000)

            # Materiale video
            material = {
                "id": material_id,
                "type": "video",
                "path": os.path.abspath(seg_info['project_path']),
                "material_name": seg_info['filename'],
                "duration": duration_us,
                "width": self.width,
                "height": self.height,
                "metetype": "local"
            }
            materials_videos.append(material)

            # Segmento video - PARTE DA 0 perché il file è già tagliato!
            segment = {
                "id": segment_id,
                "material_id": material_id,
                "target_timerange": {
                    "start": current_time,
                    "duration": duration_us
                },
                "source_timerange": {
                    "start": 0,  # Inizia da 0 perché il video è già tagliato
                    "duration": duration_us
                },
                "speed": 1.0,
                "volume": 1.0,
                "enable_adjust": True,
                "enable_color_correct_adjust": False,
                "enable_color_curves": True,
                "enable_color_match_adjust": False,
                "enable_color_wheels": True,
                "enable_lut": True,
                "enable_smart_color_adjust": False,
                "reverse": False,
                "visible": True,
                "clip": {
                    "alpha": 1.0,
                    "flip": {"horizontal": False, "vertical": False},
                    "rotation": 0.0,
                    "scale": {"x": 1.0, "y": 1.0},
                    "transform": {"x": 0.0, "y": 0.0}
                },
                "uniform_scale": {"on": True, "value": 1.0},
                "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
                "last_nonzero_volume": 1.0,
                "track_attribute": 0,
                "track_render_index": 0,
                "common_keyframes": [],
                "keyframe_refs": [],
                "extra_material_refs": []
            }
            segments.append(segment)
            current_time += duration_us

        # Draft info completo
        draft_info = {
            "id": draft_id,
            "draft_type": "video",
            "duration": self.project_duration,
            "fps": 30.0,
            "canvas_config": {
                "width": self.width,
                "height": self.height,
                "ratio": "original"
            },
            "tracks": [
                {
                    "type": "video",
                    "segments": segments
                }
            ],
            "materials": {
                "videos": materials_videos,
                "audios": [],
                "texts": [],
                "stickers": [],
                "effects": [],
                "transitions": [],
                "filters": [],
                "speeds": [],
                "time_marks": [],
                "beats": [],
                "placeholders": [],
                "images": [],
                "canvases": [],
                "audio_effects": [],
                "video_effects": [],
                "audio_fades": [],
                "shapes": []
            },
            "relationships": [],
            "version": 360000,
            "new_version": "147.0.0",
            "platform": {
                "app_id": 359289,
                "app_source": "cc",
                "app_version": "7.4.0",
                "os": "mac"
            }
        }

        draft_info_path = os.path.join(project_path, "draft_info.json")
        with open(draft_info_path, 'w', encoding='utf-8') as f:
            json.dump(draft_info, f, indent=2, ensure_ascii=False)

    def _create_minimal_structure(self, project_path: str) -> None:
        """Crea una struttura minima del progetto CapCut"""
        # Crea sottocartelle necessarie
        for folder in ['assets/video', 'assets/audio', 'assets/image',
                      'Resources', 'adjust_mask', 'common_attachment',
                      'matting', 'qr_upload', 'smart_crop', 'subdraft']:
            os.makedirs(os.path.join(project_path, folder), exist_ok=True)

        # Crea file necessari
        with open(os.path.join(project_path, 'draft_settings'), 'w') as f:
            f.write('{"draft_auto_save_status":true,"draft_save_status":true}')

        with open(os.path.join(project_path, 'performance_opt_info.json'), 'w') as f:
            f.write('{"performance_opt":false}')

        with open(os.path.join(project_path, '.locked'), 'w') as f:
            f.write('')

    def _create_meta_info(self, project_path: str, project_name: str) -> None:
        """Crea il file draft_meta_info.json con tutti i campi necessari"""
        draft_id = str(uuid.uuid4()).upper()
        current_time = int(datetime.now().timestamp())
        current_time_ms = int(datetime.now().timestamp() * 1000000)

        # Crea lista materiali per draft_meta_info
        draft_materials = []

        # Type 0 = video materials
        video_materials = []
        for seg_info in self.segment_files:
            video_materials.append({
                "create_time": current_time,
                "duration": int(seg_info['duration'] * 1000000),
                "extra_info": seg_info['filename'],
                "file_Path": os.path.abspath(seg_info['project_path']),
                "height": self.height,
                "width": self.width,
                "id": str(uuid.uuid4()),
                "import_time": current_time,
                "import_time_ms": current_time_ms,
                "item_source": 1,
                "md5": "",
                "metetype": "local",
                "roughcut_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "sub_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "type": "video"
            })

        draft_materials.append({
            "type": 0,  # video
            "value": video_materials
        })

        # Altri types vuoti
        for i in [1, 2, 3, 6, 7, 8]:
            draft_materials.append({"type": i, "value": []})

        meta_info = {
            "cloud_draft_cover": True,
            "cloud_draft_sync": True,
            "cloud_package_completed_time": "",
            "draft_cloud_capcut_purchase_info": "",
            "draft_cloud_last_action_download": False,
            "draft_cloud_package_type": "",
            "draft_cloud_purchase_info": "",
            "draft_cloud_template_id": "",
            "draft_cloud_tutorial_info": "",
            "draft_cloud_videocut_purchase_info": "",
            "draft_cover": "",
            "draft_deeplink_url": "",
            "draft_enterprise_info": {
                "draft_enterprise_extra": "",
                "draft_enterprise_id": "",
                "draft_enterprise_name": "",
                "enterprise_material": []
            },
            "draft_fold_path": os.path.abspath(project_path),
            "draft_id": draft_id,
            "draft_is_ae_produce": False,
            "draft_is_ai_packaging_used": False,
            "draft_is_ai_shorts": False,
            "draft_is_ai_translate": False,
            "draft_is_article_video_draft": False,
            "draft_is_cloud_temp_draft": False,
            "draft_is_from_deeplink": "false",
            "draft_is_invisible": False,
            "draft_materials": draft_materials,
            "draft_name": project_name,
            "draft_removable_storage_device": "",
            "draft_root_path": str(Path(project_path).parent),
            "draft_timeline_materials": [],
            "tm_draft_create": current_time_ms,
            "tm_draft_modified": current_time_ms,
            "tm_duration": self.project_duration
        }

        meta_info_path = os.path.join(project_path, "draft_meta_info.json")
        with open(meta_info_path, 'w', encoding='utf-8') as f:
            json.dump(meta_info, f, indent=2, ensure_ascii=False)


def create_capcut_project_with_cuts(video_path: str,
                                    kept_segments: List[Tuple[float, float]],
                                    video_info: Dict,
                                    project_name: str = None,
                                    capcut_dir: str = None,
                                    template_project: str = None) -> str:
    """
    Funzione helper per creare un progetto CapCut con video pre-tagliati

    :param video_path: Percorso del video originale
    :param kept_segments: Lista di segmenti da mantenere [(start, end), ...]
    :param video_info: Informazioni video da ffprobe
    :param project_name: Nome del progetto (opzionale, usa nome video se None)
    :param capcut_dir: Directory progetti CapCut (opzionale, usa default se None)
    :param template_project: Nome progetto esistente da clonare (opzionale, usa più recente se None)
    :return: Percorso del progetto creato
    """
    import tempfile

    # Usa nome video se non specificato
    if project_name is None:
        project_name = Path(video_path).stem

    # Ottieni dimensioni video
    video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
    width = int(video_stream.get('width', 1920)) if video_stream else 1920
    height = int(video_stream.get('height', 1080)) if video_stream else 1080

    # Crea directory temporanea per i segmenti
    temp_dir = tempfile.mkdtemp(prefix='capcut_segments_')

    try:
        # Crea builder e taglia i segmenti
        builder = CapCutProjectBuilder(width, height)
        builder.add_video_segments(video_path, kept_segments, video_info, temp_dir)

        # Salva progetto (copia i segmenti nel progetto)
        project_path = builder.save_to_capcut_folder(project_name, capcut_dir, template_project)

        return project_path

    finally:
        # Pulisci i file temporanei (opzionale, i segmenti sono già stati copiati)
        import shutil as sh
        try:
            sh.rmtree(temp_dir)
        except:
            pass  # Ignora errori di pulizia
