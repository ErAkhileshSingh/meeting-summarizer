package com.meetingsummarizer

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.TimeUnit

/**
 * Downloads ML models on first app launch
 * 
 * Models:
 * - Whisper Tiny (~75MB) - For speech-to-text
 * - T5-small ONNX (~120MB) - For summarization
 */
class ModelDownloader(private val context: Context) {
    
    companion object {
        private const val TAG = "ModelDownloader"
        
        // Whisper model for transcription
        const val WHISPER_MODEL_URL = 
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
        const val WHISPER_MODEL_NAME = "ggml-tiny.bin"
        const val WHISPER_MODEL_SIZE = 75_000_000L // ~75MB
        
        // T5-small ONNX for summarization (encoder + decoder)
        const val T5_ENCODER_URL = 
            "https://huggingface.co/xenova/t5-small/resolve/main/onnx/encoder_model.onnx"
        const val T5_DECODER_URL = 
            "https://huggingface.co/xenova/t5-small/resolve/main/onnx/decoder_model.onnx"
        const val T5_ENCODER_NAME = "t5-small-encoder.onnx"
        const val T5_DECODER_NAME = "t5-small-decoder.onnx"
        const val T5_ENCODER_SIZE = 60_000_000L // ~60MB
        const val T5_DECODER_SIZE = 60_000_000L // ~60MB
        
        // Tokenizer files
        const val T5_TOKENIZER_URL = 
            "https://huggingface.co/xenova/t5-small/resolve/main/tokenizer.json"
        const val T5_TOKENIZER_NAME = "t5-tokenizer.json"
    }
    
    private val modelsDir = File(context.filesDir, "models")
    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(600, TimeUnit.SECONDS) // Longer timeout for large files
        .build()
    
    /**
     * Check if all required models are downloaded
     */
    fun areModelsReady(): Boolean {
        val whisperModel = File(modelsDir, WHISPER_MODEL_NAME)
        val whisperReady = whisperModel.exists() && whisperModel.length() > 30_000_000
        return whisperReady && areSummarizationModelsReady()
    }
    
    /**
     * Check if summarization models are downloaded
     */
    fun areSummarizationModelsReady(): Boolean {
        val encoder = File(modelsDir, T5_ENCODER_NAME)
        val decoder = File(modelsDir, T5_DECODER_NAME)
        val tokenizer = File(modelsDir, T5_TOKENIZER_NAME)
        
        // Check existence and minimal size (e.g. > 1MB for models) to ensure not corrupt
        val encoderValid = encoder.exists() && encoder.length() > 1_000_000
        val decoderValid = decoder.exists() && decoder.length() > 1_000_000
        val tokenizerValid = tokenizer.exists() && tokenizer.length() > 100
        
        return encoderValid && decoderValid && tokenizerValid
    }
    
    /**
     * Download all required models
     */
    suspend fun downloadModels(onProgress: (Int) -> Unit) {
        withContext(Dispatchers.IO) {
            modelsDir.mkdirs()
            
            // Calculate total size for progress
            val totalSize = WHISPER_MODEL_SIZE + T5_ENCODER_SIZE + T5_DECODER_SIZE
            var downloadedTotal = 0L
            
            // 1. Download Whisper model
            Log.d(TAG, "Downloading Whisper model...")
            downloadFile(
                url = WHISPER_MODEL_URL,
                outputFile = File(modelsDir, WHISPER_MODEL_NAME),
                onProgress = { bytes ->
                    downloadedTotal = bytes
                    onProgress(((downloadedTotal * 100) / totalSize).toInt().coerceAtMost(33))
                }
            )
            
            // 2. Download T5 Encoder
            Log.d(TAG, "Downloading T5 encoder...")
            downloadFile(
                url = T5_ENCODER_URL,
                outputFile = File(modelsDir, T5_ENCODER_NAME),
                onProgress = { bytes ->
                    val progress = WHISPER_MODEL_SIZE + bytes
                    onProgress(((progress * 100) / totalSize).toInt().coerceIn(33, 66))
                }
            )
            
            // 3. Download T5 Decoder
            Log.d(TAG, "Downloading T5 decoder...")
            downloadFile(
                url = T5_DECODER_URL,
                outputFile = File(modelsDir, T5_DECODER_NAME),
                onProgress = { bytes ->
                    val progress = WHISPER_MODEL_SIZE + T5_ENCODER_SIZE + bytes
                    onProgress(((progress * 100) / totalSize).toInt().coerceIn(66, 99))
                }
            )
            
            // 4. Download Tokenizer
            Log.d(TAG, "Downloading T5 tokenizer...")
            downloadFile(
                url = T5_TOKENIZER_URL,
                outputFile = File(modelsDir, T5_TOKENIZER_NAME),
                onProgress = { _ -> onProgress(100) }
            )
            
            Log.d(TAG, "All models downloaded successfully!")
        }
    }
    
    /**
     * Download only Whisper model (for minimal setup)
     */
    suspend fun downloadWhisperOnly(onProgress: (Int) -> Unit) {
        withContext(Dispatchers.IO) {
            modelsDir.mkdirs()
            downloadFile(
                url = WHISPER_MODEL_URL,
                outputFile = File(modelsDir, WHISPER_MODEL_NAME),
                onProgress = { bytes ->
                    onProgress(((bytes * 100) / WHISPER_MODEL_SIZE).toInt())
                }
            )
        }
    }
    
    private fun downloadFile(
        url: String,
        outputFile: File,
        onProgress: (Long) -> Unit
    ) {
        // Skip if already exists
        if (outputFile.exists() && outputFile.length() > 1000) {
            Log.d(TAG, "File already exists: ${outputFile.name}")
            onProgress(outputFile.length())
            return
        }
        
        Log.d(TAG, "Downloading: $url")
        
        val request = Request.Builder().url(url).build()
        val response = client.newCall(request).execute()
        
        if (!response.isSuccessful) {
            throw Exception("Download failed: ${response.code} for $url")
        }
        
        val body = response.body ?: throw Exception("Empty response")
        var downloadedBytes = 0L
        
        FileOutputStream(outputFile).use { output ->
            body.byteStream().use { input ->
                val buffer = ByteArray(8192)
                var bytesRead: Int
                
                while (input.read(buffer).also { bytesRead = it } != -1) {
                    output.write(buffer, 0, bytesRead)
                    downloadedBytes += bytesRead
                    onProgress(downloadedBytes)
                }
            }
        }
        
        Log.d(TAG, "Downloaded: ${outputFile.name} (${downloadedBytes / 1024 / 1024} MB)")
    }
    
    /**
     * Get total model size in MB
     */
    fun getTotalModelSizeMB(): Int {
        return ((WHISPER_MODEL_SIZE + T5_ENCODER_SIZE + T5_DECODER_SIZE) / 1024 / 1024).toInt()
    }
}
