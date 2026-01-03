package com.meetingsummarizer

import android.content.Context
import java.io.File

/**
 * JNI wrapper for whisper.cpp
 * Handles native model loading and transcription
 */
class WhisperLib(private val context: Context) {
    
    private var nativeHandle: Long = 0
    private val modelPath: String
        get() = File(context.filesDir, "models/ggml-tiny.bin").absolutePath
    
    init {
        // Load the JNI wrapper library (which links to libwhisper internally)
        System.loadLibrary("whisper-jni")
    }
    
    /**
     * Load the whisper model
     */
    fun loadModel(): Boolean {
        val modelFile = File(modelPath)
        if (!modelFile.exists()) {
            throw IllegalStateException("Model not found: $modelPath")
        }
        nativeHandle = nativeLoadModel(modelPath)
        return nativeHandle != 0L
    }
    
    /**
     * Transcribe audio file to text
     * @param audioPath Path to 16kHz WAV file
     * @return Transcribed text
     */
    fun transcribe(audioPath: String): String {
        if (nativeHandle == 0L) {
            throw IllegalStateException("Model not loaded")
        }
        return nativeTranscribe(nativeHandle, audioPath)
    }
    
    /**
     * Release native resources
     */
    fun release() {
        if (nativeHandle != 0L) {
            nativeFreeModel(nativeHandle)
            nativeHandle = 0
        }
    }
    
    // Native JNI methods
    private external fun nativeLoadModel(modelPath: String): Long
    private external fun nativeTranscribe(handle: Long, audioPath: String): String
    private external fun nativeFreeModel(handle: Long)
    
    companion object {
        const val MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
        const val MODEL_SIZE_MB = 40
    }
}
