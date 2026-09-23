# AutoVideoMaker

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg)
![Deepgram](https://img.shields.io/badge/Deepgram-AI-brightgreen.svg)
![OpenAI Whisper](https://img.shields.io/badge/Whisper-AI-orange.svg)
![Claude](https://img.shields.io/badge/Claude_Opus_5-AI-purple.svg)
![GPT Images](https://img.shields.io/badge/GPT_Images_2-AI-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-AI-red.svg)

**Professional automated video editing tool powered by AI.**

AutoVideoMaker is an intelligent video processing tool that automatically removes silences and pauses from your recordings, making them more dynamic and engaging. Using advanced AI services like Deepgram (default transcription), Whisper, Claude Opus 5 (metadata) and GPT Images 2 (thumbnails), it goes beyond simple cutting by separating vocals from background noise, generating accurate transcriptions for subtitles, and creating professional YouTube thumbnails with your own image integrated into them.

The tool produces optimized metadata including titles, descriptions, and tags for your YouTube uploads, while also generating EDL files compatible with Premiere Pro for professional editing workflows. Whether you're processing a single video or batch-processing entire folders with dozens of files, AutoVideoMaker handles everything automatically with robust error handling and intelligent processing.

Perfect for content creators, podcasters, YouTubers, and video editing professionals who want to save hours of manual editing work.

---

## Table of Contents

- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Setup](#setup)
  - [Quick Method](#quick-method-recommended)
  - [Manual Setup](#manual-setup)
  - [Deepgram API Configuration](#3-configure-deepgram-api-default-transcription)
  - [Anthropic & OpenAI API Configuration](#4-configure-anthropic--openai-api-optional)
  - [Profile Image Configuration](#5-configure-profile-image-optional)
- [Usage](#usage)
  - [Recommended Method (run.sh)](#recommended-method-with-runsh)
  - [Practical Examples](#practical-examples)
- [Output](#output)
- [How It Works](#how-it-works)
  - [Processing Pipeline](#processing-pipeline)
  - [Real-World Use Cases](#real-world-use-cases)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## Key Features

### Complete Automation
- **Zero manual configuration** - Automatic setup with one script
- **Intelligent processing** - AI detects and removes only significant silences
- **Batch processing** - Process entire folders with glob patterns (`*.mp4`, `**/*.mp4`)
- **Robust error handling** - Continue processing even if one video fails

### Professional Quality
- **AI vocal separation** - Removes background noise while keeping voice crystal clear
- **Accurate transcriptions** - Deepgram API by default (fast, cloud-based) or Whisper AI locally
- **Custom thumbnails** - Integrate your profile image into thumbnails
- **Professional export** - Ready-to-open CapCut project + EDL files for Premiere Pro with precise timeline

### Performance and Flexibility
- **Customizable parameters** - Silence threshold, minimum duration, merge distance
- **Fast mode** - Disable AI for rapid processing
- **Multi-format** - Supports MP4, AVI, MOV, MKV, FLV, WMV, WebM, M4V
- **Organized output** - Separate folders for each video with all assets

## Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd AutoVideoMaker

# 2. Make script executable
chmod +x run.sh

# 3. Run with your video (automatically installs everything)
./run.sh your_video.mp4
```

Done! The `run.sh` script automatically handles installation and execution.

## Setup

### Quick Method (Recommended)

Use the `run.sh` script that automatically installs everything:

```bash
# Make script executable (only first time)
chmod +x run.sh

# Run with your video
./run.sh video.mp4
```

The script automatically:
- Verifies Python 3 and FFmpeg
- Creates virtual environment
- Installs all dependencies
- Starts processing

### Manual Setup

If you prefer manual installation:

#### 1. Install system dependencies

```bash
# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Windows
# Download ffmpeg from https://ffmpeg.org/download.html
```

#### 2. Create virtual environment and install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Configure Deepgram API (default transcription)

Deepgram is the **default transcription service**: it's fast (cloud API) and doesn't require downloading local models.

1. **Get your free API key** ($200 free credit):
   - Go to [Deepgram Console](https://console.deepgram.com/signup)
   - Create a new API key
   - Copy the key

2. **Copy the example file and add your key:**
   ```bash
   cp .env.example .env
   ```
   ```bash
   DEEPGRAM_API_KEY=your-deepgram-api-key-here
   ```

**Note:** If `DEEPGRAM_API_KEY` is not configured (or Deepgram fails), the tool automatically falls back to local Whisper transcription. You can also force Whisper with `--transcriber whisper`.

#### 4. Configure Anthropic & OpenAI API (optional)

To generate AI metadata and automatic thumbnails:

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Get your API keys:**
   - **Anthropic** (text metadata with Claude Opus 5): [console.anthropic.com](https://console.anthropic.com/)
   - **OpenAI** (thumbnails with GPT Images 2): [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

3. **Edit the `.env` file:**
   ```bash
   ANTHROPIC_API_KEY=your-anthropic-api-key-here
   OPENAI_API_KEY=your-openai-api-key-here
   ```

**Note:** If you don't configure Anthropic, the tool will skip AI metadata and thumbnail generation. If you configure only Anthropic (without OpenAI), text metadata will be generated but the thumbnail will be skipped.

#### 5. Configure profile image (optional)

To include your image in YouTube thumbnails:

1. **Prepare the image:**
   - File name: `personal_image.png`
   - Format: PNG with transparent or neutral background
   - Image requirements:
     - Neutral gaze towards camera
     - Straight frontal pose
     - Preferably neutral or removable background
     - Minimum resolution: 500x500 px
     - Ideal: professional profile photo or portrait

2. **Place the file:**
   ```bash
   # Copy your image to the project root
   cp /path/to/your/photo.png personal_image.png
   ```

**Best practices examples:**
- GOOD: Profile photo on white/gray background
- GOOD: Frontal portrait with gaze towards camera
- GOOD: Good lighting and quality
- BAD: Angled or profile photos
- BAD: Backgrounds too complex or colorful
- BAD: Dynamic poses or excessive expressions

If you don't provide the image, thumbnails will be generated with graphic elements only.

## Usage

### Recommended Method (with run.sh)

The `run.sh` script automatically manages the virtual environment and dependencies:

```bash
# Single video
./run.sh video.mp4

# Multiple videos
./run.sh video1.mp4 video2.mp4 video3.mp4

# Using glob patterns
./run.sh *.mp4
./run.sh videos/**/*.mp4

# With custom options
./run.sh *.mp4 -t -35 -d 0.3 --no-whisper
```

### Direct Method (with Python)

If the virtual environment is already active:

```bash
# Activate virtual environment
source venv/bin/activate

# Single video
python3 main.py your_video.mp4

# Multiple videos
python3 main.py video1.mp4 video2.mp4 video3.mp4

# Using glob patterns
python3 main.py *.mp4
python3 main.py videos/**/*.mp4
```

### Available Options

```bash
./run.sh video1.mp4 video2.mp4 \
  -t -40 \              # Silence threshold in dB (default: -40)
  -d 0.5 \              # Minimum silence duration in seconds (default: 0.5)
  -m 1.0 \              # Max distance to merge silences (default: 1.0)
  --transcriber whisper \  # Transcription service: deepgram (default) or whisper
  --whisper-model medium \ # Whisper model: tiny, base, small, medium, large
  --language it            # Transcription language (default: it)
  --cut-mode auto \        # Cut method: auto, speech (word timestamps) or silence
  --word-gap 0.2 \         # Max gap between words in same speech segment (default: 0.2s)
  --speech-pad 0.05 \     # Safety margin at speech segment edges (default: 0.05s)
  --capcut-single-project \ # One combined CapCut project for all videos
  --capcut-name MyProject   # Name of the combined CapCut project
  --cleanup full \          # Take cleanup: full (rules + Claude), rules, off
  --cue-word rifaccio \     # Cue word that discards the take just flubbed ("" disables it)
  --retranscribe \          # Ignore the saved words.json and transcribe again
  --no-metadata             # Skip AI title, description and thumbnail
```

### CapCut export modes

- **Default**: each video gets its own CapCut project (named after the file)
- **`--capcut-single-project`**: with multiple videos, generates **one combined CapCut project** with all cut clips in sequence on the same timeline. The project is named after the first video unless `--capcut-name` is used:
  ```bash
  ./run.sh clip1.mp4 clip2.mp4 clip3.mp4 --capcut-single-project --capcut-name MyVlog
  ```

### Cut methods

- **`speech`** (default when transcription is available): cuts are based on **word-level timestamps** from the transcription (Deepgram/Whisper). Cuts happen exactly between words - never mid-word - and remove breaths, coughs and long pauses. A safety pad protects word attack/release at the edges.
- **`silence`**: cuts based on FFmpeg `silencedetect` volume analysis (use `-t`/`-d`/`-m` to tune). Used automatically as fallback with `--no-transcription` or when word timestamps are unavailable.
- **`auto`** (default): uses `speech` when word timestamps are available, otherwise `silence`.

### Take cleanup

On top of pauses, AutoVideoMaker removes the typical mistakes of an unscripted recording:

- **False starts**: a sentence interrupted and restarted right away ("Buongiorno a... Ciao a tutti")
- **Stutters**: words repeated by mistake ("delle delle", "che che")
- **Repeated takes**: the same sentence said again; the last complete version is kept
- **Takes marked with the cue word**: say **"rifaccio"** on its own, between two pauses, then repeat the sentence; the flubbed take and the cue word are removed

Content is never judged: anything you say only once stays in the video.

Deterministic rules find the candidates; Claude (`claude-opus-5`) reviews the uncertain ones and finds rephrased self-corrections. Claude only points at word numbers: cut times come from the word timestamps, at the quietest point of each pause.

Uncertain cuts are applied **and marked**: the CapCut project gets a timeline marker on each of them, titled with the cut type and the removed text so you can tell it from your own markers. To undo one, drag the edge of the clip at the marker. Every cut is listed with its context in `pulizia.md` and `pulizia.json`.

| Option | Description |
|---|---|
| `--cleanup full` | Rules + Claude (default, needs `ANTHROPIC_API_KEY`, about $0.30 for a 20-minute video) |
| `--cleanup rules` | Rules only, free |
| `--cleanup off` | Pauses only, as before |
| `--cue-word WORD` | Cue word (default `rifaccio`; `--cue-word ""` disables it) |
| `--retranscribe` | Ignore the saved `words.json` and transcribe again |
| `--no-metadata` | Skip AI title, description and thumbnail (useful for test runs) |

The transcription is saved in `output/<video>/words.json` and reused when you process the same video again, with no new Deepgram call. CapCut projects are never overwritten: a second run creates `<name>-2`.

### Choose the transcription service

By default, transcription uses **Deepgram** (requires `DEEPGRAM_API_KEY` in `.env`). To use local Whisper instead:

```bash
./run.sh video.mp4 --transcriber whisper --whisper-model medium
```

### Disable transcription and AI metadata

For faster processing without transcription and AI metadata:

```bash
./run.sh *.mp4 --no-transcription
```

(`--no-whisper` is still supported as an alias for backward compatibility)

### Supported Video Formats

The tool automatically supports the following formats:
- `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.m4v`

### Practical Examples

#### Single processing with complete AI
```bash
# Complete setup with metadata and thumbnail
./run.sh my_video.mp4
```

#### Fast batch processing
```bash
# Process all MP4 videos without AI (faster)
./run.sh *.mp4 --no-transcription
```

#### Processing with custom parameters
```bash
# More aggressive silence threshold to remove more pauses
./run.sh video.mp4 -t -35 -d 0.3 -m 0.5
```

#### Recursive folder processing
```bash
# Process all videos in subfolders
./run.sh videos/**/*.mp4
```

## Output

The tool generates an `output/{video_name}/` folder containing:

- `chunks/` - Cut video segments
- `premiere_pro.edl` - EDL file for Premiere Pro editing
- **CapCut project** - A ready-to-open project (named after the video file) automatically created in the CapCut drafts folder (`~/Movies/CapCut/User Data/Projects/com.lveditor.draft/`). Just open CapCut: the project appears in the home with the cut timeline (video + audio linked)
- `transcript.txt` - Complete video transcription (if transcription enabled)
- `words.json` - Word-level transcription with timestamps (reused on the next run)
- `pulizia.md` / `pulizia.json` - Take cleanup report: every cut with type, context and reason
- `metadata.txt` - AI-generated title, description, tags with Claude Opus 5 (if Anthropic configured)
- `thumbnail.png` - AI-generated YouTube thumbnail with GPT Images 2 (if OpenAI configured)
- `prompt.txt` - Prompt used to generate the thumbnail
- `{video_name}.mp4` - Original video moved to folder

## How It Works

### Processing Pipeline

1. **Audio extraction** - Extracts and cleans audio from video
2. **AI vocal separation** - Isolates voice from background noise (optional)
3. **AI transcription** - Complete transcription with word-level timestamps via Deepgram (default) or Whisper (optional)
4. **Cut analysis** - Precise speech segments from word timestamps, or silence detection via FFmpeg as fallback
5. **Video cutting** - Creates video segments removing silences
6. **NLE export** - Generates a CapCut project (auto-imported in the app) and an EDL file for Premiere Pro
7. **AI metadata** - Generates title, description, tags with Claude Opus 5 and thumbnail with GPT Images 2 (optional)

### Real-World Use Cases

#### YouTuber / Content Creator
**Problem:** Hours of editing to remove pauses and "uhms" from videos
**Solution:** Batch process videos with one command, get cut videos + thumbnails + metadata
```bash
./run.sh recordings/*.mp4
```

#### Podcaster
**Problem:** Long silences between questions/answers, background noise
**Solution:** Automatic silence removal + AI vocal separation + transcriptions for show notes
```bash
./run.sh episode.mp4 -t -35 -d 0.5
```

#### Professional Editor
**Problem:** Pre-editing raw footage for clean timelines
**Solution:** EDL export for Premiere Pro with all cuts already marked
```bash
./run.sh rushes/*.mp4 --no-transcription  # Fast, cuts only
```

#### Trainer / Teacher
**Problem:** Recorded lessons with long pauses and noise
**Solution:** Optimized videos + automatic transcriptions for students
```bash
./run.sh lessons/**/*.mp4 --whisper-model large
```

#### Gaming Content Creator
**Problem:** Hours of gameplay to condense, need for catchy thumbnails
**Solution:** Pause removal + custom thumbnails with your face
```bash
./run.sh gameplay.mp4 -t -40 -d 1.0  # Keeps more content
```

## Requirements

- Python 3.8+
- FFmpeg
- Deepgram API key (default transcription, free at [console.deepgram.com](https://console.deepgram.com/signup)) - optional, falls back to Whisper
- ~5 GB of free space for AI models (Whisper/vocal separation, downloaded on first use)

## Testing

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

Manual check in CapCut (repeat after every CapCut major update: the draft format is reverse-engineered, tested with CapCut 9.4 on macOS):

1. Close CapCut, run `./run.sh video.mov`, open CapCut: the project shows up in the home with today's date.
2. Open it: no "damaged project" warning and no missing media.
3. Timeline markers sit on the joins of the uncertain cuts, titled with the cut type and the removed text.
4. Drag the edge of the clip at a marker: the removed piece comes back.
5. Edit something, save and reopen: CapCut keeps the project.

## Troubleshooting

### FFmpeg not found
Make sure ffmpeg is installed and in PATH:
```bash
ffmpeg -version
```

### Whisper import error
```bash
pip install openai-whisper
```

### Anthropic / OpenAI API error
Verify that `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are correct in `.env` file