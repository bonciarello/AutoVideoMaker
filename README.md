# AutoVideoMaker

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg)
![OpenAI Whisper](https://img.shields.io/badge/Whisper-AI-orange.svg)
![Google Gemini](https://img.shields.io/badge/Gemini-AI-purple.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-AI-red.svg)

**Professional automated video editing tool powered by AI.**

AutoVideoMaker is an intelligent video processing tool that automatically removes silences and pauses from your recordings, making them more dynamic and engaging. Using advanced AI models like Whisper and Gemini, it goes beyond simple cutting by separating vocals from background noise, generating accurate transcriptions for subtitles, and creating professional YouTube thumbnails with your own image integrated into them.

The tool produces optimized metadata including titles, descriptions, and tags for your YouTube uploads, while also generating EDL files compatible with Premiere Pro for professional editing workflows. Whether you're processing a single video or batch-processing entire folders with dozens of files, AutoVideoMaker handles everything automatically with robust error handling and intelligent processing.

Perfect for content creators, podcasters, YouTubers, and video editing professionals who want to save hours of manual editing work.

---

## Table of Contents

- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Setup](#setup)
  - [Quick Method](#quick-method-recommended)
  - [Manual Setup](#manual-setup)
  - [Gemini API Configuration](#3-configure-gemini-api-optional)
  - [Profile Image Configuration](#4-configure-profile-image-optional)
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
- **Accurate transcriptions** - Whisper AI for broadcast-quality subtitles
- **Custom thumbnails** - Integrate your profile image into thumbnails
- **Professional export** - EDL files for Premiere Pro with precise timeline

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

**Want a step-by-step guide?** Check [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) for a complete setup checklist.

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

#### 3. Configure Gemini API (optional)

To generate AI metadata and automatic thumbnails:

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Get your free API key:**
   - Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Copy the key

3. **Edit the `.env` file:**
   ```bash
   GEMINI_API_KEY=your-api-key-here
   ```

**Note:** If you don't configure Gemini, the tool will still work but will skip metadata and AI thumbnail generation.

#### 4. Configure profile image (optional)

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
  --whisper-model medium  # Whisper model: tiny, base, small, medium, large
```

### Disable Whisper and AI metadata

For faster processing without transcription and AI metadata:

```bash
./run.sh *.mp4 --no-whisper
```

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
./run.sh *.mp4 --no-whisper --whisper-model tiny
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
- `transcript.txt` - Complete video transcription (if Whisper enabled)
- `metadata.txt` - AI-generated title, description, tags (if Gemini configured)
- `thumbnail.png` - AI-generated YouTube thumbnail (if Gemini configured)
- `prompt.txt` - Prompt used to generate the thumbnail
- `{video_name}.mp4` - Original video moved to folder

## How It Works

### Processing Pipeline

1. **Audio extraction** - Extracts and cleans audio from video
2. **AI vocal separation** - Isolates voice from background noise (optional)
3. **Silence analysis** - Detects silence intervals using FFmpeg
4. **Whisper transcription** - Generates complete transcription (optional)
5. **Video cutting** - Creates video segments removing silences
6. **EDL export** - Generates Premiere Pro compatible files
7. **AI metadata** - Generates title, description, tags and thumbnail with Gemini (optional)

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
./run.sh rushes/*.mp4 --no-whisper  # Fast, cuts only
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
- ~5 GB of free space for AI models (automatically downloaded on first use)

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

### Gemini API error
Verify that `GEMINI_API_KEY` is correct in `.env` file