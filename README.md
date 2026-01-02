# ⚡ Meeting Summary App

Fast video-to-summary pipeline that processes 1-hour meetings in ~5 minutes using AI.

## Features

- 🎥 **Video to Audio**: Extract audio from any video format (MP4, AVI, MKV, etc.)
- 🎙️ **Fast Transcription**: Uses faster-whisper (4-8x faster than OpenAI Whisper)
- 📝 **AI Summarization**: DistilBART generates structured summaries with:
  - Executive summary
  - Detailed breakdown
  - Key points
  - Action items
- 🖥️ **Modern GUI**: Dark-themed Tkinter interface with progress tracking

## Quick Setup (New Device)

### Windows (Easiest)
1. Make sure Python 3.8+ is installed
2. Double-click `setup.bat`
3. Wait for installation to complete
4. Run `python fast_video_app.py`

### Manual Setup (All Platforms)
```bash
# Clone/download this project, then:
cd MeetingSummary

# Run the setup script
python setup.py

# Or install manually:
pip install -r requirements.txt
```

### Check Dependencies Only
```bash
python setup.py --check
```

## Requirements

### Automatic (via setup.py)
- Python 3.8+
- faster-whisper
- transformers + torch
- scipy, numpy

### Manual Installation Required
- **FFmpeg**: Required for video processing
  - Windows: Setup script can install automatically, or download from [ffmpeg.org](https://ffmpeg.org/download.html)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg`

## Usage

```bash
python fast_video_app.py
```

1. Click **Select Video File** to choose a video
2. Adjust settings (model size, summary length)
3. Click **Generate Transcript & Summary**
4. Wait for processing (~5 min for 1-hour video)
5. Save transcript and summary

## Project Structure

```
MeetingSummary/
├── fast_video_app.py    # Main GUI application
├── setup.py             # Automated setup script
├── setup.bat            # Windows quick setup (double-click)
├── requirements.txt     # Python dependencies
├── src/
│   ├── video_processor.py   # FFmpeg audio extraction
│   ├── fast_transcriber.py  # faster-whisper transcription
│   └── summarizer.py        # DistilBART summarization
├── models/              # Downloaded ML models (auto-created)
├── outputs/             # Saved transcripts/summaries
└── temp/                # Temporary audio files (auto-cleaned)
```

## Model Sizes

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | ~39 MB | Fastest | Basic |
| base | ~74 MB | Very Fast | Good |
| **small** | ~244 MB | Fast | High (Default) |
| medium | ~769 MB | Moderate | Very High |

## Troubleshooting

### FFmpeg not found
- Run `python setup.py --check` to verify FFmpeg
- Windows: Add `C:\ffmpeg\bin` to system PATH
- Restart your terminal/IDE after installing

### Out of memory
- Use a smaller Whisper model (tiny/base)
- Close other applications
- Process shorter videos

### Slow processing
- Use GPU if available (faster-whisper supports CUDA)
- Reduce chunk size in settings
- Use smaller model

## License

MIT License - Free for personal and commercial use.
