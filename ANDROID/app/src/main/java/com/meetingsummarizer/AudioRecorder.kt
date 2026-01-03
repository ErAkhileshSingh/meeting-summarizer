package com.meetingsummarizer

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import androidx.core.content.ContextCompat
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Audio recorder that captures audio and saves as 16kHz WAV file
 * suitable for Whisper transcription
 */
class AudioRecorder(private val context: Context) {
    
    companion object {
        private const val TAG = "AudioRecorder"
        private const val SAMPLE_RATE = 16000  // Whisper expects 16kHz
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    }
    
    private var audioRecord: AudioRecord? = null
    private var isRecording = false
    private var recordingThread: Thread? = null
    private var outputFile: File? = null
    private var pcmData = mutableListOf<Byte>()
    
    /**
     * Check if we have recording permission
     */
    fun hasPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context, 
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    /**
     * Start recording audio
     * @param onAmplitude Callback for real-time amplitude updates (for visualization)
     */
    @Throws(SecurityException::class)
    fun startRecording(onAmplitude: ((Int) -> Unit)? = null): Boolean {
        if (isRecording) {
            Log.w(TAG, "Already recording")
            return false
        }
        
        if (!hasPermission()) {
            Log.e(TAG, "No recording permission")
            return false
        }
        
        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        if (bufferSize == AudioRecord.ERROR || bufferSize == AudioRecord.ERROR_BAD_VALUE) {
            Log.e(TAG, "Invalid buffer size: $bufferSize")
            return false
        }
        
        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                CHANNEL_CONFIG,
                AUDIO_FORMAT,
                bufferSize * 2
            )
            
            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                Log.e(TAG, "AudioRecord not initialized")
                audioRecord?.release()
                audioRecord = null
                return false
            }
            
            // Create output file with timestamp
            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
            outputFile = File(context.filesDir, "recordings/recording_$timestamp.wav")
            outputFile?.parentFile?.mkdirs()
            
            pcmData.clear()
            isRecording = true
            audioRecord?.startRecording()
            
            // Start recording thread
            recordingThread = thread {
                val buffer = ByteArray(bufferSize)
                
                while (isRecording) {
                    val bytesRead = audioRecord?.read(buffer, 0, bufferSize) ?: 0
                    
                    if (bytesRead > 0) {
                        // Store PCM data
                        synchronized(pcmData) {
                            for (i in 0 until bytesRead) {
                                pcmData.add(buffer[i])
                            }
                        }
                        
                        // Calculate amplitude for visualization
                        onAmplitude?.let { callback ->
                            val amplitude = calculateAmplitude(buffer, bytesRead)
                            callback(amplitude)
                        }
                    }
                }
            }
            
            Log.d(TAG, "Recording started: ${outputFile?.absolutePath}")
            return true
            
        } catch (e: SecurityException) {
            Log.e(TAG, "Security exception: ${e.message}")
            throw e
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording: ${e.message}", e)
            return false
        }
    }
    
    /**
     * Stop recording and save WAV file
     * @return The recorded WAV file, or null if failed
     */
    fun stopRecording(): File? {
        if (!isRecording) {
            Log.w(TAG, "Not recording")
            return null
        }
        
        isRecording = false
        recordingThread?.join(1000)
        
        try {
            audioRecord?.stop()
            audioRecord?.release()
            audioRecord = null
            
            // Save as WAV file
            val pcmBytes: ByteArray
            synchronized(pcmData) {
                pcmBytes = pcmData.toByteArray()
            }
            
            if (pcmBytes.isEmpty()) {
                Log.w(TAG, "No audio data recorded")
                return null
            }
            
            outputFile?.let { file ->
                writeWavFile(file, pcmBytes)
                Log.d(TAG, "Recording saved: ${file.absolutePath} (${file.length()} bytes)")
                return file
            }
            
        } catch (e: Exception) {
            Log.e(TAG, "Failed to stop recording: ${e.message}", e)
        }
        
        return null
    }
    
    /**
     * Cancel recording without saving
     */
    fun cancelRecording() {
        isRecording = false
        recordingThread?.join(1000)
        
        try {
            audioRecord?.stop()
            audioRecord?.release()
            audioRecord = null
            pcmData.clear()
            outputFile?.delete()
            outputFile = null
        } catch (e: Exception) {
            Log.e(TAG, "Error canceling recording: ${e.message}")
        }
    }
    
    /**
     * Get recording duration in seconds
     */
    fun getRecordingDurationSeconds(): Float {
        synchronized(pcmData) {
            // 16-bit = 2 bytes per sample
            val samples = pcmData.size / 2
            return samples.toFloat() / SAMPLE_RATE
        }
    }
    
    /**
     * Check if currently recording
     */
    fun isRecording(): Boolean = isRecording
    
    /**
     * Get current recorded audio as a temporary WAV file for live transcription.
     * This allows transcribing without stopping the recording.
     */
    fun getCurrentAudioWavFile(): File? {
        if (!isRecording && pcmData.isEmpty()) {
            return null
        }
        
        try {
            val pcmBytes: ByteArray
            synchronized(pcmData) {
                if (pcmData.isEmpty()) return null
                pcmBytes = pcmData.toByteArray()
            }
            
            // Create a temporary file for current audio
            val tempFile = File(context.cacheDir, "live_audio_temp.wav")
            writeWavFile(tempFile, pcmBytes)
            Log.d(TAG, "Created temp audio file: ${tempFile.length()} bytes")
            return tempFile
            
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create temp audio file: ${e.message}")
            return null
        }
    }
    
    /**
     * Calculate amplitude from audio buffer (0-100)
     */
    private fun calculateAmplitude(buffer: ByteArray, size: Int): Int {
        var sum = 0L
        val shortBuffer = ByteBuffer.wrap(buffer, 0, size)
            .order(ByteOrder.LITTLE_ENDIAN)
            .asShortBuffer()
        
        while (shortBuffer.hasRemaining()) {
            val sample = shortBuffer.get().toInt()
            sum += sample * sample
        }
        
        val rms = Math.sqrt(sum.toDouble() / (size / 2))
        // Normalize to 0-100 range (32768 is max for 16-bit audio)
        return ((rms / 32768.0) * 100).toInt().coerceIn(0, 100)
    }
    
    /**
     * Write PCM data to WAV file with proper header
     */
    private fun writeWavFile(file: File, pcmData: ByteArray) {
        FileOutputStream(file).use { fos ->
            val dataSize = pcmData.size
            val channels = 1  // Mono
            val bitsPerSample = 16
            val byteRate = SAMPLE_RATE * channels * bitsPerSample / 8
            val blockAlign = channels * bitsPerSample / 8
            
            // RIFF header
            fos.write("RIFF".toByteArray())
            fos.write(intToBytes(36 + dataSize))
            fos.write("WAVE".toByteArray())
            
            // fmt chunk
            fos.write("fmt ".toByteArray())
            fos.write(intToBytes(16))  // Subchunk1Size for PCM
            fos.write(shortToBytes(1)) // AudioFormat (PCM = 1)
            fos.write(shortToBytes(channels.toShort()))
            fos.write(intToBytes(SAMPLE_RATE))
            fos.write(intToBytes(byteRate))
            fos.write(shortToBytes(blockAlign.toShort()))
            fos.write(shortToBytes(bitsPerSample.toShort()))
            
            // data chunk
            fos.write("data".toByteArray())
            fos.write(intToBytes(dataSize))
            fos.write(pcmData)
        }
    }
    
    private fun intToBytes(value: Int): ByteArray {
        return byteArrayOf(
            value.toByte(),
            (value shr 8).toByte(),
            (value shr 16).toByte(),
            (value shr 24).toByte()
        )
    }
    
    private fun shortToBytes(value: Short): ByteArray {
        return byteArrayOf(
            value.toByte(),
            (value.toInt() shr 8).toByte()
        )
    }
    
    /**
     * Get list of all saved recordings
     */
    fun getSavedRecordings(): List<File> {
        val recordingsDir = File(context.filesDir, "recordings")
        return recordingsDir.listFiles { file -> 
            file.extension == "wav" 
        }?.sortedByDescending { it.lastModified() } ?: emptyList()
    }
    
    /**
     * Delete a recording
     */
    fun deleteRecording(file: File): Boolean {
        return file.delete()
    }
}
