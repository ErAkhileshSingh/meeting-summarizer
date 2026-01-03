#include <jni.h>
#include <string>
#include <vector>
#include <fstream>
#include <cstdint>
#include <android/log.h>
#include "whisper.h"

#define LOG_TAG "WhisperJNI"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

/**
 * Read WAV file and extract PCM samples as float
 * Supports 16-bit PCM WAV files (the format we create from AudioProcessor)
 */
static bool read_wav_file(const std::string &path, std::vector<float> &pcmf32, int &sample_rate) {
    std::ifstream file(path, std::ios::binary);
    if (!file.is_open()) {
        LOGE("Failed to open WAV file: %s", path.c_str());
        return false;
    }
    
    // Read RIFF header
    char riff[4];
    file.read(riff, 4);
    if (strncmp(riff, "RIFF", 4) != 0) {
        LOGE("Not a valid RIFF file");
        return false;
    }
    
    // Skip file size
    file.seekg(4, std::ios::cur);
    
    // Read WAVE header
    char wave[4];
    file.read(wave, 4);
    if (strncmp(wave, "WAVE", 4) != 0) {
        LOGE("Not a valid WAVE file");
        return false;
    }
    
    // Find fmt chunk
    while (file.good()) {
        char chunk_id[4];
        file.read(chunk_id, 4);
        
        uint32_t chunk_size;
        file.read(reinterpret_cast<char*>(&chunk_size), 4);
        
        if (strncmp(chunk_id, "fmt ", 4) == 0) {
            uint16_t audio_format;
            file.read(reinterpret_cast<char*>(&audio_format), 2);
            
            if (audio_format != 1) {
                LOGE("Unsupported audio format: %d (only PCM supported)", audio_format);
                return false;
            }
            
            uint16_t num_channels;
            file.read(reinterpret_cast<char*>(&num_channels), 2);
            
            uint32_t sr;
            file.read(reinterpret_cast<char*>(&sr), 4);
            sample_rate = sr;
            
            // Skip byte rate and block align
            file.seekg(6, std::ios::cur);
            
            uint16_t bits_per_sample;
            file.read(reinterpret_cast<char*>(&bits_per_sample), 2);
            
            LOGD("WAV format: %d channels, %d Hz, %d bits", num_channels, sample_rate, bits_per_sample);
            
            // Skip any extra format bytes
            if (chunk_size > 16) {
                file.seekg(chunk_size - 16, std::ios::cur);
            }
        } else if (strncmp(chunk_id, "data", 4) == 0) {
            // Read PCM data
            std::vector<int16_t> pcm16(chunk_size / 2);
            file.read(reinterpret_cast<char*>(pcm16.data()), chunk_size);
            
            // Convert to float [-1.0, 1.0]
            pcmf32.resize(pcm16.size());
            for (size_t i = 0; i < pcm16.size(); i++) {
                pcmf32[i] = static_cast<float>(pcm16[i]) / 32768.0f;
            }
            
            LOGD("Loaded %zu audio samples", pcmf32.size());
            return true;
        } else {
            // Skip unknown chunk
            file.seekg(chunk_size, std::ios::cur);
        }
    }
    
    LOGE("No data chunk found in WAV file");
    return false;
}

extern "C" {

/**
 * Load whisper model from file
 */
JNIEXPORT jlong JNICALL
Java_com_meetingsummarizer_WhisperLib_nativeLoadModel(
    JNIEnv *env,
    jobject /* this */,
    jstring modelPath
) {
    const char *path = env->GetStringUTFChars(modelPath, nullptr);
    LOGD("Loading model from: %s", path);
    
    struct whisper_context_params cparams = whisper_context_default_params();
    cparams.use_gpu = false;  // CPU only for Android
    
    struct whisper_context *ctx = whisper_init_from_file_with_params(path, cparams);
    
    env->ReleaseStringUTFChars(modelPath, path);
    
    if (ctx == nullptr) {
        LOGE("Failed to load model");
        return 0;
    }
    
    LOGD("Model loaded successfully");
    return reinterpret_cast<jlong>(ctx);
}

/**
 * Transcribe audio file
 */
JNIEXPORT jstring JNICALL
Java_com_meetingsummarizer_WhisperLib_nativeTranscribe(
    JNIEnv *env,
    jobject /* this */,
    jlong handle,
    jstring audioPath
) {
    auto *ctx = reinterpret_cast<struct whisper_context *>(handle);
    const char *path = env->GetStringUTFChars(audioPath, nullptr);
    
    LOGD("Transcribing: %s", path);
    
    // Load WAV file
    std::vector<float> pcmf32;
    int sample_rate = 16000;
    
    if (!read_wav_file(path, pcmf32, sample_rate)) {
        env->ReleaseStringUTFChars(audioPath, path);
        return env->NewStringUTF("Error: Failed to load audio file");
    }
    
    env->ReleaseStringUTFChars(audioPath, path);
    
    // Check sample rate (Whisper expects 16kHz)
    if (sample_rate != 16000) {
        LOGE("Warning: Sample rate is %d Hz, Whisper expects 16000 Hz", sample_rate);
        // Continue anyway - our AudioProcessor should have resampled
    }
    
    // Set transcription parameters
    struct whisper_full_params wparams = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    wparams.print_realtime = false;
    wparams.print_progress = false;
    wparams.print_timestamps = false;
    wparams.single_segment = false;
    wparams.n_threads = 4;
    wparams.language = "en";
    wparams.translate = false;
    
    LOGD("Starting transcription with %zu samples...", pcmf32.size());
    
    // Run transcription
    int result = whisper_full(ctx, wparams, pcmf32.data(), pcmf32.size());
    
    if (result != 0) {
        LOGE("Whisper transcription failed with code: %d", result);
        return env->NewStringUTF("Error: Transcription failed");
    }
    
    // Collect results
    std::string transcript;
    int n_segments = whisper_full_n_segments(ctx);
    
    LOGD("Transcription complete: %d segments", n_segments);
    
    for (int i = 0; i < n_segments; i++) {
        const char *text = whisper_full_get_segment_text(ctx, i);
        transcript += text;
        transcript += " ";
    }
    
    LOGD("Transcript length: %zu characters", transcript.length());
    
    return env->NewStringUTF(transcript.c_str());
}

/**
 * Free model resources
 */
JNIEXPORT void JNICALL
Java_com_meetingsummarizer_WhisperLib_nativeFreeModel(
    JNIEnv *env,
    jobject /* this */,
    jlong handle
) {
    auto *ctx = reinterpret_cast<struct whisper_context *>(handle);
    if (ctx != nullptr) {
        whisper_free(ctx);
        LOGD("Model freed");
    }
}

} // extern "C"
