package com.meetingsummarizer

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Audio extraction and processing utilities
 * Extracts audio from video and converts to 16kHz WAV for Whisper
 */
object AudioProcessor {
    
    private const val TAG = "AudioProcessor"
    private const val TARGET_SAMPLE_RATE = 16000
    private const val TARGET_CHANNELS = 1
    private const val BITS_PER_SAMPLE = 16
    
    /**
     * Extract audio from video and convert to 16kHz mono WAV for Whisper
     */
    fun extractAudio(context: Context, videoFile: File): File {
        val outputFile = File(context.cacheDir, "audio_16khz.wav")
        
        Log.d(TAG, "Extracting audio from: ${videoFile.absolutePath}")
        
        try {
            extractAndConvertToWav(videoFile, outputFile)
            Log.d(TAG, "Audio extracted successfully: ${outputFile.length()} bytes")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to extract audio: ${e.message}", e)
            throw e
        }
        
        return outputFile
    }
    
    /**
     * Extract audio from video, decode to PCM, and save as WAV
     */
    private fun extractAndConvertToWav(videoFile: File, outputFile: File) {
        val extractor = MediaExtractor()
        var decoder: MediaCodec? = null
        
        try {
            extractor.setDataSource(videoFile.absolutePath)
            
            // Find audio track
            var audioTrackIndex = -1
            var audioFormat: MediaFormat? = null
            
            for (i in 0 until extractor.trackCount) {
                val format = extractor.getTrackFormat(i)
                val mime = format.getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("audio/")) {
                    audioTrackIndex = i
                    audioFormat = format
                    Log.d(TAG, "Found audio track $i: $mime")
                    break
                }
            }
            
            if (audioTrackIndex == -1 || audioFormat == null) {
                throw IllegalArgumentException("No audio track found in video")
            }
            
            extractor.selectTrack(audioTrackIndex)
            
            val mime = audioFormat.getString(MediaFormat.KEY_MIME)!!
            val sampleRate = audioFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            val channelCount = audioFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            
            Log.d(TAG, "Audio format: $mime, $sampleRate Hz, $channelCount channels")
            
            // Create decoder
            decoder = MediaCodec.createDecoderByType(mime)
            decoder.configure(audioFormat, null, null, 0)
            decoder.start()
            
            // Collect all PCM data
            val pcmData = mutableListOf<Byte>()
            val bufferInfo = MediaCodec.BufferInfo()
            var isEOS = false
            
            while (!isEOS) {
                // Feed input to decoder
                val inputBufferIndex = decoder.dequeueInputBuffer(10000)
                if (inputBufferIndex >= 0) {
                    val inputBuffer = decoder.getInputBuffer(inputBufferIndex)!!
                    val sampleSize = extractor.readSampleData(inputBuffer, 0)
                    
                    if (sampleSize < 0) {
                        decoder.queueInputBuffer(
                            inputBufferIndex, 0, 0, 0,
                            MediaCodec.BUFFER_FLAG_END_OF_STREAM
                        )
                    } else {
                        decoder.queueInputBuffer(
                            inputBufferIndex, 0, sampleSize,
                            extractor.sampleTime, 0
                        )
                        extractor.advance()
                    }
                }
                
                // Get decoded output
                val outputBufferIndex = decoder.dequeueOutputBuffer(bufferInfo, 10000)
                if (outputBufferIndex >= 0) {
                    if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                        isEOS = true
                    }
                    
                    if (bufferInfo.size > 0) {
                        val outputBuffer = decoder.getOutputBuffer(outputBufferIndex)!!
                        val chunk = ByteArray(bufferInfo.size)
                        outputBuffer.get(chunk)
                        pcmData.addAll(chunk.toList())
                    }
                    
                    decoder.releaseOutputBuffer(outputBufferIndex, false)
                }
            }
            
            Log.d(TAG, "Decoded ${pcmData.size} bytes of PCM data")
            
            // Convert to 16kHz mono if needed
            val convertedPcm = convertPcm(
                pcmData.toByteArray(),
                sampleRate, channelCount,
                TARGET_SAMPLE_RATE, TARGET_CHANNELS
            )
            
            // Write WAV file
            writeWavFile(outputFile, convertedPcm, TARGET_SAMPLE_RATE, TARGET_CHANNELS)
            
            Log.d(TAG, "WAV file created: ${outputFile.length()} bytes")
            
        } finally {
            decoder?.stop()
            decoder?.release()
            extractor.release()
        }
    }
    
    /**
     * Convert PCM data to target sample rate and channel count
     */
    private fun convertPcm(
        input: ByteArray,
        srcSampleRate: Int,
        srcChannels: Int,
        dstSampleRate: Int,
        dstChannels: Int
    ): ByteArray {
        // Convert bytes to shorts (16-bit samples)
        val shortBuffer = ByteBuffer.wrap(input)
            .order(ByteOrder.LITTLE_ENDIAN)
            .asShortBuffer()
        
        val samples = ShortArray(shortBuffer.remaining())
        shortBuffer.get(samples)
        
        // Convert to mono if needed
        val monoSamples = if (srcChannels > 1) {
            ShortArray(samples.size / srcChannels) { i ->
                var sum = 0
                for (ch in 0 until srcChannels) {
                    sum += samples[i * srcChannels + ch]
                }
                (sum / srcChannels).toShort()
            }
        } else {
            samples
        }
        
        // Resample if needed
        val resampledSamples = if (srcSampleRate != dstSampleRate) {
            val ratio = srcSampleRate.toDouble() / dstSampleRate
            val newLength = (monoSamples.size / ratio).toInt()
            ShortArray(newLength) { i ->
                val srcIndex = (i * ratio).toInt().coerceIn(0, monoSamples.size - 1)
                monoSamples[srcIndex]
            }
        } else {
            monoSamples
        }
        
        // Convert back to bytes
        val output = ByteArray(resampledSamples.size * 2)
        val outputBuffer = ByteBuffer.wrap(output).order(ByteOrder.LITTLE_ENDIAN)
        resampledSamples.forEach { outputBuffer.putShort(it) }
        
        Log.d(TAG, "Converted PCM: ${samples.size} -> ${resampledSamples.size} samples")
        
        return output
    }
    
    /**
     * Write PCM data to WAV file with proper header
     */
    private fun writeWavFile(file: File, pcmData: ByteArray, sampleRate: Int, channels: Int) {
        FileOutputStream(file).use { fos ->
            val dataSize = pcmData.size
            val byteRate = sampleRate * channels * BITS_PER_SAMPLE / 8
            val blockAlign = channels * BITS_PER_SAMPLE / 8
            
            // RIFF header
            fos.write("RIFF".toByteArray())
            fos.write(intToBytes(36 + dataSize))
            fos.write("WAVE".toByteArray())
            
            // fmt chunk
            fos.write("fmt ".toByteArray())
            fos.write(intToBytes(16)) // Subchunk1Size (PCM)
            fos.write(shortToBytes(1)) // AudioFormat (PCM = 1)
            fos.write(shortToBytes(channels.toShort()))
            fos.write(intToBytes(sampleRate))
            fos.write(intToBytes(byteRate))
            fos.write(shortToBytes(blockAlign.toShort()))
            fos.write(shortToBytes(BITS_PER_SAMPLE.toShort()))
            
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
}
