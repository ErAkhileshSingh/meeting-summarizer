# 📱 Meeting Summarizer - Android App

On-device video/audio transcription and summarization using **whisper.cpp** and **extractive summarization**.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Android App (Kotlin)                      │
├─────────────────────────────────────────────────────────────┤
│  MainActivity.kt           - UI & orchestration              │
│  AudioProcessor.kt         - Extract audio from video        │
│  WhisperLib.kt            - JNI wrapper for whisper.cpp      │
│  T5Summarizer.kt          - Text summarization               │
│  ModelDownloader.kt       - Download models on first launch  │
├─────────────────────────────────────────────────────────────┤
│                    Native Layer (C++)                        │
├─────────────────────────────────────────────────────────────┤
│  whisper-jni.cpp          - JNI bindings for Whisper         │
│  whisper.cpp (submodule)  - Speech-to-text engine            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 Models Used

| Component | Model | Size | Source |
|-----------|-------|------|--------|
| **Transcription** | whisper.cpp (ggml-tiny) | ~75 MB | [HuggingFace](https://huggingface.co/ggerganov/whisper.cpp) |
| **Summarization** | T5-small (ONNX) | ~120 MB | [HuggingFace](https://huggingface.co/xenova/t5-small) |

### Models Downloaded on First Launch:

| File | Size | Purpose |
|------|------|---------|
| `ggml-tiny.bin` | ~75 MB | Whisper speech-to-text |
| `t5-small-encoder.onnx` | ~60 MB | T5 encoder for summarization |
| `t5-small-decoder.onnx` | ~60 MB | T5 decoder for summarization |
| `t5-tokenizer.json` | ~1 MB | Tokenizer vocabulary |
| **Total Download** | **~196 MB** | |

### Why These Models?

- **whisper.cpp**: Native C++ implementation of OpenAI Whisper, optimized for mobile CPUs
- **T5-small ONNX**: Google's T5 model fine-tuned for summarization, converted to ONNX for mobile inference

---

## 📁 Project Structure

```
ANDROID/
├── app/
│   ├── src/main/
│   │   ├── cpp/                          # Native C++ code
│   │   │   ├── whisper/                  # whisper.cpp submodule
│   │   │   ├── whisper-jni.cpp          # JNI bindings
│   │   │   └── CMakeLists.txt           # Native build config
│   │   │
│   │   ├── java/com/meetingsummarizer/
│   │   │   ├── MainActivity.kt          # Main UI activity
│   │   │   ├── WhisperLib.kt           # Whisper JNI wrapper
│   │   │   ├── T5Summarizer.kt         # Summarization logic
│   │   │   ├── AudioProcessor.kt       # Audio extraction
│   │   │   └── ModelDownloader.kt      # Model download manager
│   │   │
│   │   ├── res/
│   │   │   ├── layout/activity_main.xml
│   │   │   └── values/
│   │   │
│   │   └── AndroidManifest.xml
│   │
│   └── build.gradle.kts                  # App-level build config
│
├── build.gradle.kts                      # Project-level build config
├── settings.gradle.kts
└── README.md                             # This file
```

---

## ⚙️ Implementation Details

### 1. Audio Extraction (`AudioProcessor.kt`)

```kotlin
// Uses MediaCodec to decode any audio format to PCM
// Converts to 16kHz mono WAV (Whisper requirement)
```

**Flow:**
1. Open video with `MediaExtractor`
2. Find audio track
3. Decode with `MediaCodec` to PCM
4. Resample to 16kHz mono
5. Write WAV file with proper header

### 2. Speech-to-Text (`whisper-jni.cpp`)

```cpp
// Load WAV file → Float samples → whisper_full() → Text segments
```

**Flow:**
1. Parse WAV header
2. Convert 16-bit PCM to float [-1.0, 1.0]
3. Run `whisper_full()` with greedy sampling
4. Collect segment texts

### 3. Summarization (`T5Summarizer.kt`)

Uses **extractive summarization** (no ML model):

```kotlin
// TF-IDF based sentence scoring
1. Split text into sentences
2. Calculate word frequencies (excluding stop words)
3. Score sentences by word importance
4. Return top N sentences
```

---

## 🔧 Build Configuration

### Native Build (`CMakeLists.txt`)

```cmake
# C++17 for whisper.cpp
set(CMAKE_CXX_STANDARD 17)

# 16KB page alignment for Android 15+
set(CMAKE_SHARED_LINKER_FLAGS "-Wl,-z,max-page-size=16384")

# Link whisper library
target_link_libraries(whisper-jni whisper log)
```

### Gradle (`build.gradle.kts`)

```kotlin
android {
    compileSdk = 34
    minSdk = 26
    
    ndk {
        abiFilters += listOf("arm64-v8a", "armeabi-v7a")
    }
    
    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
        }
    }
}

dependencies {
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.19.0")
    // ... other deps
}
```

---

## 📲 App Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Select Video │ ──► │ Extract Audio│ ──► │  Transcribe  │ ──► │  Summarize   │
│              │     │  (16kHz WAV) │     │  (Whisper)   │     │ (Extractive) │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

1. **User selects video** via file picker
2. **Audio extracted** using MediaCodec → 16kHz mono WAV
3. **Transcribed** using whisper.cpp (native C++)
4. **Summarized** using TF-IDF extractive algorithm

---

## 🚀 First Launch

On first launch:
1. App downloads `ggml-tiny.bin` (~40MB) from HuggingFace
2. Model saved to `files/models/` directory
3. Subsequent launches use cached model

---

## 📊 Performance

| Operation | Device (Snapdragon 8 Gen 2) | Notes |
|-----------|---------------------------|-------|
| Audio Extraction | ~2-5 sec | Depends on video length |
| Transcription | ~30 sec/min | whisper-tiny model |
| Summarization | ~100 ms | CPU-only, no ML |

---

## 🔮 Future Improvements

- [ ] Add recording functionality
- [ ] Support Hindi/Hinglish (Oriserve Whisper model)
- [ ] Add ONNX-based T5 summarization
- [ ] Background processing with WorkManager
- [ ] Export/share functionality

---

## 📝 License

MIT License - Free for personal and commercial use.
