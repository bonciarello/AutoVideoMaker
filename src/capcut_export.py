#!/usr/bin/env python3
"""
Export progetto CapCut
Genera un progetto CapCut desktop (draft_info.json + draft_meta_info.json)
con la timeline contenente il video già tagliato (silenzi rimossi).

Il progetto viene scritto direttamente nella cartella dei draft di CapCut
(~/Movies/CapCut/User Data/Projects/com.lveditor.draft/) così appare
automaticamente nella home dell'app.

Formato verificato con CapCut 9.x (macOS). I tempi sono in microsecondi.
"""

import os
import json
import time
import uuid
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from utils import parse_fps

# Cartella dei draft di CapCut su macOS
CAPCUT_DRAFTS_ROOT = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)

MICROSECONDS = 1_000_000


def _uuid() -> str:
    return str(uuid.uuid4()).upper()


def _sec_to_us(seconds: float) -> int:
    """Converte secondi in microsecondi (unità di tempo dei draft CapCut)."""
    return int(round(seconds * MICROSECONDS))


def _seconds_to_frame_us(seconds: float, fps: float) -> int:
    """
    Converte secondi in microsecondi SNAPpati al frame più vicino.

    CapCut quantizza internamente ogni tempo della timeline al frame
    (verificato su progetti reali: source/target timerange sono sempre
    multipli di 1/fps). Se scriviamo microsecondi "grezzi", CapCut li
    riallinea alla sua griglia: sui bordi di clip molto corti o a metà
    frame il riallineamento può collassare il source_timerange.start a 0
    (la clip parte dall'inizio del video invece che dal taglio voluto).
    Snap esplicito => nessun riallineamento a sorpresa.
    """
    if fps <= 0:
        return _sec_to_us(seconds)
    frame_us = MICROSECONDS / fps
    frame_index = int(round(seconds * fps))
    return int(round(frame_index * frame_us))


def _duration_us(start_us: int, end_us: int, fps: float) -> int:
    """
    Durata in microsecondi, garantendo almeno un frame e coerenza
    con la griglia (source_end resta un multiplo di 1/fps).
    """
    duration = max(end_us - start_us, int(round(MICROSECONDS / fps)) if fps > 0 else 1)
    return duration


def _build_video_material(video_path: str, video_info: Dict, material_uuid: str,
                          fps: float = 0.0) -> Dict:
    """Costruisce il materiale video che punta al file sorgente (path assoluto)."""
    video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), {})
    audio_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'audio'), None)
    # Durata allineata alla griglia del progetto, come ogni altro tempo del
    # draft: evita riallineamenti di CapCut sul bordo finale del materiale.
    duration_us = _seconds_to_frame_us(float(video_info['format']['duration']), fps)

    return {
        "id": material_uuid,
        "unique_id": "",
        "type": "video",
        "duration": duration_us,
        "path": os.path.abspath(video_path),
        "media_path": "",
        "local_id": "",
        "has_audio": audio_stream is not None,
        "reverse_path": "",
        "intensifies_path": "",
        "reverse_intensifies_path": "",
        "intensifies_audio_path": "",
        "cartoon_path": "",
        "width": int(video_stream.get('width', 1920)),
        "height": int(video_stream.get('height', 1080)),
        "category_id": "",
        "category_name": "local",
        "material_id": "",
        "material_name": Path(video_path).name,
        "material_url": "",
        "crop": {
            "upper_left_x": 0.0, "upper_left_y": 0.0,
            "upper_right_x": 1.0, "upper_right_y": 0.0,
            "lower_left_x": 0.0, "lower_left_y": 1.0,
            "lower_right_x": 1.0, "lower_right_y": 1.0
        },
        "crop_ratio": "free",
        "audio_fade": None,
        "crop_scale": 1.0,
        "extra_type_option": 0,
        "stable": None,
        "matting": None,
        "source": 0,
        "source_platform": 0,
        "formula_id": "",
        "check_flag": 125892607,
        "video_algorithm": {"algorithms": []},
        "freeze": None,
        "smart_motion": None,
        "picture_from": "none",
        "picture_set_category_id": "",
        "picture_set_category_name": "",
        "request_id": "",
        "team_id": "",
        "is_ai_generate_content": False,
        "is_copyright": False,
        "is_text_edit_overdub": False,
        "is_unified_beauty_mode": False,
        "has_sound_separated": False,
        "aigc_history_id": "",
        "aigc_item_id": "",
        "aigc_type": "none",
        "local_material_from": 0,
        "origin_material_id": "",
        "multi_camera_info": None,
        "content_feature_info": None
    }


def _build_helper_materials() -> Tuple[Dict[str, list], List[str]]:
    """
    Crea i materiali di servizio referenziati dai segmenti (extra_material_refs).
    Un'unica istanza condivisa da tutti i segmenti.
    """
    speed_id = _uuid()
    placeholder_id = _uuid()
    canvas_id = _uuid()
    animation_id = _uuid()
    channel_mapping_id = _uuid()
    color_id = _uuid()
    vocal_sep_id = _uuid()

    materials = {
        "speeds": [{
            "id": speed_id, "type": "speed", "mode": 0,
            "speed": 1.0, "curve_speed": None
        }],
        "placeholder_infos": [{
            "id": placeholder_id, "type": "placeholder_info", "meta_type": "none",
            "res_path": "", "res_text": "", "error_path": "", "error_text": ""
        }],
        "canvases": [{
            "id": canvas_id, "type": "canvas_color", "color": "", "blur": 0.0,
            "image": "", "album_image": "", "image_id": "", "image_name": "",
            "source_platform": 0, "team_id": ""
        }],
        "material_animations": [{
            "id": animation_id, "type": "sticker_animation",
            "animations": [], "multi_language_current": "none"
        }],
        "sound_channel_mappings": [{
            "id": channel_mapping_id, "type": "none",
            "audio_channel_mapping": 0, "is_config_open": False
        }],
        "material_colors": [{
            "id": color_id, "is_color_clip": False, "is_gradient": False,
            "solid_color": "", "gradient_colors": [], "gradient_percents": [],
            "gradient_angle": 90.0, "width": 0.0, "height": 0.0
        }],
        "vocal_separations": [{
            "id": vocal_sep_id, "type": "vocal_separation", "choice": 0,
            "removed_sounds": [], "time_range": None, "production_path": "",
            "final_algorithm": "", "enter_from": ""
        }]
    }

    ref_ids = [speed_id, placeholder_id, canvas_id, animation_id,
               channel_mapping_id, color_id, vocal_sep_id]
    return materials, ref_ids


def _build_segment(material_uuid: str,
                   source_start_us: int, source_end_us: int,
                   target_start_us: int,
                   extra_refs: List[str],
                   duration_us: int) -> Dict:
    """Costruisce un segmento di timeline (un taglio mantenuto)."""
    return {
        "id": _uuid(),
        "material_id": material_uuid,
        "source_timerange": {"start": source_start_us, "duration": duration_us},
        "target_timerange": {"start": target_start_us, "duration": duration_us},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "",
        "state": 0,
        "speed": 1.0,
        "is_loop": False,
        "is_tone_modify": False,
        "reverse": False,
        "intensifies_audio": False,
        "cartoon": False,
        "volume": 1.0,
        "last_nonzero_volume": 1.0,
        "clip": {
            "scale": {"x": 1.0, "y": 1.0},
            "rotation": 0.0,
            "transform": {"x": 0.0, "y": 0.0},
            "flip": {"vertical": False, "horizontal": False},
            "alpha": 1.0
        },
        "uniform_scale": {"on": True, "value": 1.0},
        "extra_material_refs": extra_refs,
        "render_index": 0,
        "keyframe_refs": [],
        "common_keyframes": [],
        "enable_lut": True,
        "enable_adjust": True,
        "enable_hsl": False,
        "enable_color_curves": True,
        "enable_hsl_curves": True,
        "enable_color_wheels": True,
        "enable_smart_color_adjust": False,
        "enable_color_match_adjust": False,
        "enable_color_correct_adjust": False,
        "enable_adjust_mask": False,
        "enable_video_mask": True,
        "enable_mask_stroke": False,
        "enable_mask_shadow": False,
        "enable_color_adjust_pro": False,
        "visible": True,
        "group_id": "",
        "track_render_index": 0,
        "track_attribute": 0,
        "is_placeholder": False,
        "template_id": "",
        "template_scene": "default",
        "hdr_settings": {"mode": 1, "intensity": 1.0, "nits": 1000},
        "caption_info": None,
        "responsive_layout": {
            "enable": False, "target_follow": "", "size_layout": 0,
            "horizontal_pos_layout": 0, "vertical_pos_layout": 0
        },
        "raw_segment_id": "",
        "lyric_keyframes": None,
        "digital_human_template_group_id": "",
        "color_correct_alg_result": "",
        "source": "segmentsourcenormal"
    }


def generate_capcut_project(clips: List[Dict],
                            project_name: str,
                            drafts_root: Optional[str] = None) -> Optional[str]:
    """
    Genera un progetto CapCut con la timeline dei video tagliati.

    Supporta clip multiple: ogni clip diventa un materiale video e i suoi
    segmenti vengono posti in sequenza sulla stessa traccia della timeline.

    :param clips: Lista di clip, ognuna un dict con:
                  - keep_ranges: segmenti mantenuti [(start, end), ...] in secondi
                  - video_path: percorso del video sorgente (linkato, non copiato)
                  - video_info: informazioni video da ffprobe
    :param project_name: Nome del progetto CapCut
    :param drafts_root: Cartella draft CapCut (default: percorso standard macOS)
    :return: Percorso della cartella progetto, o None se errore
    """
    clips = [c for c in clips if c.get("keep_ranges")]
    if not clips:
        print("Nessun segmento da esportare nel progetto CapCut.")
        return None

    root = drafts_root or CAPCUT_DRAFTS_ROOT
    if not os.path.isdir(root):
        print(f"Cartella draft CapCut non trovata: {root}")
        print("   CapCut non installato o mai avviato. Progetto non generato.")
        return None

    project_dir = os.path.join(root, project_name)
    os.makedirs(project_dir, exist_ok=True)

    # Canvas e fps dal primo video (CapCut gestisce materiali misti)
    first_stream = next((s for s in clips[0]["video_info"]['streams'] if s['codec_type'] == 'video'), {})
    fps = parse_fps(first_stream)
    width = int(first_stream.get('width', 1920))
    height = int(first_stream.get('height', 1080))

    # CapCut quantizza ogni tempo della timeline al frame del progetto (fps
    # globale qui sotto). Lo snap dei bordi va però fatto sulla griglia del
    # frame: se il progetto gira a 60fps ma una clip sorgente è a 25fps, il
    # taglio viene comunque agganciato alla griglia del PROGETTO, che è
    # quella che CapCut usa per riallineare i segmenti.
    frame_us = MICROSECONDS / fps if fps > 0 else MICROSECONDS
    min_duration_us = int(round(frame_us)) if fps > 0 else 1

    # Segnala clip con fps diverso da quello del progetto: il progetto usa
    # un solo fps (canvas), quindi i tagli di quelle clip vengono agganciati
    # alla griglia del progetto e possono spostarsi di qualche frame.
    for clip in clips:
        clip_stream = next((s for s in clip["video_info"]['streams'] if s['codec_type'] == 'video'), None)
        clip_fps = parse_fps(clip_stream, fps)
        if abs(clip_fps - fps) > 0.01:
            print(f"Attenzione: {Path(clip['video_path']).name} gira a {clip_fps:.2f}fps "
                  f"ma il progetto è a {fps:.2f}fps: i tagli saranno agganciati alla "
                  "griglia del progetto.")

    helper_materials, extra_refs = _build_helper_materials()

    materials = {
        "audio_balances": [], "audio_effects": [], "audio_fades": [],
        "audio_track_indexes": [], "audios": [], "beats": [],
        "canvases": helper_materials["canvases"], "chromas": [],
        "color_curves": [], "digital_humans": [], "drafts": [],
        "effects": [], "flowers": [], "green_screens": [], "handwrites": [],
        "hsl": [], "images": [], "log_color_wheels": [], "loudnesses": [],
        "manual_deformations": [], "masks": [],
        "material_animations": helper_materials["material_animations"],
        "material_colors": helper_materials["material_colors"],
        "multi_language_refs": [],
        "placeholder_infos": helper_materials["placeholder_infos"],
        "plugin_effects": [], "primary_color_wheels": [],
        "realtime_denoises": [], "shapes": [], "smart_crops": [],
        "smart_relights": [],
        "sound_channel_mappings": helper_materials["sound_channel_mappings"],
        "speeds": helper_materials["speeds"], "stickers": [],
        "tail_leaders": [], "text_templates": [], "texts": [],
        "time_marks": [], "transitions": [], "video_effects": [],
        "video_trackings": [],
        "vocal_beautifys": [],
        "vocal_separations": helper_materials["vocal_separations"],
        "videos": []
    }

    # Materiali video e segmenti: per ogni clip un materiale, i suoi segmenti
    # in sequenza sulla traccia (source = pezzo del video originale,
    # target = posizione cumulativa nella timeline)
    segments = []
    target_start_us = 0

    for clip in clips:
        material_uuid = _uuid()
        video_material = _build_video_material(
            clip["video_path"], clip["video_info"], material_uuid, fps
        )
        materials["videos"].append(video_material)

        for start, end in clip["keep_ranges"]:
            # Snap al frame: il taglio viene allineato alla griglia del
            # progetto, così l'inizio clip non può scivolare a 0.
            source_start_us = _seconds_to_frame_us(start, fps)
            source_end_us = _seconds_to_frame_us(end, fps)
            if source_end_us <= source_start_us:
                source_end_us = source_start_us + min_duration_us

            clip_duration_us = _duration_us(source_start_us, source_end_us, fps)
            segments.append(_build_segment(
                material_uuid, source_start_us, source_end_us,
                target_start_us, extra_refs, clip_duration_us
            ))
            target_start_us += clip_duration_us

    total_duration_us = target_start_us

    tracks = [{
        "attribute": 0,
        "flag": 0,
        "id": _uuid(),
        "is_default_name": True,
        "name": "",
        "segments": segments,
        "type": "video"
    }]

    now = int(time.time())
    # NOTA: tm_draft_create/tm_draft_modified sono in MICROSECONDI
    # (verificato su progetti reali CapCut 9.x: valori ~1.78e15).
    # Con i millisecondi CapCut mostrerebbe la data 21/01/1970.
    now_us = now * MICROSECONDS
    draft_id = _uuid()

    platform_info = {
        "os": "mac",
        "os_version": "26.5.1",
        "app_id": 359289,
        "app_version": "9.1.0",
        "app_source": "cc",
        "device_id": uuid.uuid4().hex,
        "hard_disk_id": "",
        "mac_address": ""
    }

    draft_info = {
        "canvas_config": {"ratio": "original", "width": width, "height": height, "background": None},
        "color_space": 0,
        "config": {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 1,
            "export_range": None,
            "extract_audio_last_index": 1,
            "lyrics_recognition_id": "",
            "lyrics_sync": True,
            "lyrics_taskinfo": [],
            "maintrack_adsorb": True,
            "material_save_mode": 0,
            "original_sound_last_index": 1,
            "record_audio_last_index": 1,
            "sticker_max_index": 1,
            "subtitle_recognition_id": "",
            "subtitle_sync": False,
            "subtitle_taskinfo": [],
            "video_mute": False,
            "voice_change_sync": False,
            "zoom_info_params": None
        },
        "cover": None,
        "create_time": now,
        "draft_type": "",
        "duration": total_duration_us,
        "extra_info": None,
        "fps": fps,
        "free_render_index_mode_on": False,
        "group_container": None,
        "id": draft_id,
        "is_drop_frame_timecode": False,
        "keyframe_graph_list": [],
        "keyframes": {
            "adjusts": [], "audios": [], "effects": [], "filters": [],
            "handwrites": [], "stickers": [], "texts": [], "videos": []
        },
        "last_modified_platform": platform_info,
        "lyrics_effects": [],
        "materials": materials,
        "mixed_track_mode_on": False,
        "mutable_config": None,
        "name": project_name,
        "new_version": "175.0.0",
        "path": project_dir,
        "platform": platform_info,
        "relationships": [],
        "render_index_track_mode_on": False,
        "retouch_cover": None,
        "smart_ads_info": None,
        "source": "default",
        "static_cover_image_path": "",
        "time_marks": None,
        "tracks": tracks,
        "uneven_animation_template_info": None,
        "update_time": now,
        "version": 360000
    }

    draft_meta_info = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "{\n}\n",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "{\n}\n",
        "draft_cloud_videocut_purchase_info": "{\"template_type\":\"\",\"unlock_type\":\"\"}",
        "draft_cover": "",
        "draft_deeplink_url": "",
        "draft_enterprise_info": {
            "draft_enterprise_extra": "",
            "draft_enterprise_id": "",
            "draft_enterprise_name": "",
            "enterprise_material": []
        },
        "draft_fold_path": project_dir,
        "draft_id": draft_id,
        "draft_is_ae_produce": False,
        "draft_is_ai_packaging_used": False,
        "draft_is_ai_shorts": False,
        "draft_is_ai_translate": False,
        "draft_is_article_video_draft": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_from_deeplink": "false",
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_materials": [{
            "type": 0,
            "value": [{
                "ai_group_type": "",
                "create_time": 0,
                "duration": vm["duration"],
                "enter_from": 0,
                "extra_info": vm["material_name"],
                "file_Path": vm["path"],
                "height": vm["height"],
                "id": str(uuid.uuid4()),
                "import_time": now,
                "import_time_ms": -1,
                "item_source": 1,
                "md5": "",
                "metetype": "video",
                "roughcut_time_range": {"start": 0, "duration": vm["duration"]},
                "sub_time_range": {"start": -1, "duration": -1},
                "type": 0,
                "width": vm["width"]
            } for vm in materials["videos"]]
        }],
        "draft_name": project_name,
        "draft_new_version": "",
        "draft_root_path": root,
        "draft_timeline_materials_size_": 0,
        "draft_type": "",
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_modified": 0,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_remove": 0,
        "tm_duration": total_duration_us
    }

    try:
        with open(os.path.join(project_dir, "draft_info.json"), 'w', encoding='utf-8') as f:
            json.dump(draft_info, f, ensure_ascii=False)
        with open(os.path.join(project_dir, "draft_meta_info.json"), 'w', encoding='utf-8') as f:
            json.dump(draft_meta_info, f, ensure_ascii=False)
    except OSError as e:
        print(f"Errore scrittura progetto CapCut: {e}")
        return None

    # Controllo di sicurezza: ogni tempo deve essere un multiplo esatto di
    # 1/fps, altrimenti CapCut riallinea i tagli (rischio inizio clip a 0).
    # La tolleranza è mezza unità di frame: a 60fps il frame non è un numero
    # intero di microsecondi (16666.666...), quindi un residuo di
    # arrotondamento di pochi us è normale e NON è un disallineamento.
    def _is_aligned(value: int) -> bool:
        if fps <= 0:
            return True
        return abs(value - round(value / frame_us) * frame_us) < frame_us / 2

    misaligned = [
        (s['source_timerange']['start'], s['target_timerange']['start'])
        for s in segments
        if not _is_aligned(s['source_timerange']['start'])
        or not _is_aligned(s['source_timerange']['duration'])
        or not _is_aligned(s['target_timerange']['start'])
        or not _is_aligned(s['target_timerange']['duration'])
    ]
    if misaligned:
        print(f"Attenzione: {len(misaligned)} segmenti non allineati al frame ({fps} fps): "
              "CapCut potrebbe riallineare i tagli.")

    print(f"Progetto CapCut generato: {project_name}")
    print(f"   ({len(materials['videos'])} clip, {len(segments)} segmenti, "
          f"{total_duration_us / MICROSECONDS:.1f}s di timeline)")
    print(f"   Apri CapCut: il progetto appare nella home.")
    return project_dir
