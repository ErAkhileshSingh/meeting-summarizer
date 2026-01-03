package com.meetingsummarizer

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.nio.LongBuffer

/**
 * T5-small ONNX summarizer
 * Handles neural network inference for text summarization
 */
class T5Summarizer(private val context: Context) {
    
    companion object {
        private const val TAG = "T5Summarizer"
        private const val MAX_INPUT_LENGTH = 512
        private const val MAX_OUTPUT_LENGTH = 150
    }
    
    private var ortEnv: OrtEnvironment? = null
    private var encoderSession: OrtSession? = null
    private var decoderSession: OrtSession? = null
    private var tokenizer: SimpleTokenizer? = null
    private var isModelLoaded = false
    
    private val modelsDir: File
        get() = File(context.filesDir, "models")
    
    private var loadError: String = ""
    
    fun loadModel(): Boolean {
        val encoderFile = File(modelsDir, "t5-small-encoder.onnx")
        val decoderFile = File(modelsDir, "t5-small-decoder.onnx")
        val tokenizerFile = File(modelsDir, "t5-tokenizer.json")
        
        if (!encoderFile.exists() || !decoderFile.exists()) {
            Log.w(TAG, "ONNX models not found")
            loadError = "Models not found in ${modelsDir.absolutePath}"
            return false
        }
        
        return try {
            ortEnv = OrtEnvironment.getEnvironment()
            val sessionOptions = OrtSession.SessionOptions().apply {
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
                setIntraOpNumThreads(4)
            }
            
            encoderSession = ortEnv?.createSession(encoderFile.absolutePath, sessionOptions)
            decoderSession = ortEnv?.createSession(decoderFile.absolutePath, sessionOptions)
            
            if (tokenizerFile.exists()) {
                tokenizer = SimpleTokenizer(tokenizerFile)
            }
            
            isModelLoaded = true
            loadError = ""
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load T5: ${e.message}")
            loadError = "Load Exception: ${e.message}"
            false
        }
    }
    
    fun summarize(text: String, maxLength: Int = MAX_OUTPUT_LENGTH): String {
        if (!isModelLoaded || encoderSession == null || decoderSession == null) {
            Log.e(TAG, "Model not loaded properly")
            return "DEBUG_ERROR: Model not loaded.\nReason: $loadError\nEncoder: $encoderSession\nDecoder: $decoderSession\n\n" + extractiveSummary(text)
        }
        
        return try {
            runT5Inference(text, maxLength)
        } catch (e: Exception) {
            Log.e(TAG, "Inference failed: ${e.message}")
            "DEBUG_ERROR: Inference failed.\nError: ${e.message}\n\n" + extractiveSummary(text)
        }
    }

    private fun runT5Inference(text: String, maxLength: Int): String {
        val env = ortEnv ?: throw IllegalStateException("Env null")
        val encoder = encoderSession ?: throw IllegalStateException("Encoder null")
        val decoder = decoderSession ?: throw IllegalStateException("Decoder null")

        // 1. Prepare Encoder Inputs with "summarize: " prefix
        val inputIds = tokenizer?.encode("summarize: $text") ?: return extractiveSummary(text)
        val truncatedIds = inputIds.take(MAX_INPUT_LENGTH).toLongArray()

        val inputShape = longArrayOf(1, truncatedIds.size.toLong())
        val inputTensor = OnnxTensor.createTensor(env, LongBuffer.wrap(truncatedIds), inputShape)
        val attentionMask = LongArray(truncatedIds.size) { 1L }
        val attentionTensor = OnnxTensor.createTensor(env, LongBuffer.wrap(attentionMask), inputShape)

        // 2. Run Encoder
        val encoderInputs = mapOf(
            "input_ids" to inputTensor, 
            "attention_mask" to attentionTensor
        )
        val encoderOutput = encoder.run(encoderInputs)
        val encoderHiddenStates = encoderOutput.get(0) as OnnxTensor

        // 3. Greedy Decoding
        val outputIds = mutableListOf<Long>()
        val currentDecoderIds = mutableListOf<Long>(0L) // Start token

        try {
            for (step in 0 until maxLength) {
                val decoderInputIdsArray = currentDecoderIds.toLongArray()
                val decoderInputTensor = OnnxTensor.createTensor(env, LongBuffer.wrap(decoderInputIdsArray), longArrayOf(1, decoderInputIdsArray.size.toLong()))

                // FIX: Explicitly typed map for decoder inputs
                val decoderInputs = mapOf(
                    "input_ids" to decoderInputTensor,
                    "encoder_hidden_states" to encoderHiddenStates,
                    "encoder_attention_mask" to attentionTensor
                )

                val decoderResult = decoder.run(decoderInputs)
                val logits = decoderResult.get(0).value
                val nextTokenId = getArgmax(logits)

                decoderResult.close()
                decoderInputTensor.close()

                if (nextTokenId == 1L) break // EOS
                outputIds.add(nextTokenId)
                currentDecoderIds.add(nextTokenId)
            }
        } finally {
            encoderOutput.close()
            inputTensor.close()
            attentionTensor.close()
        }

        val decodedText = tokenizer?.decode(outputIds) ?: ""

        if (decodedText.isBlank()) {
            val vocabSize = tokenizer?.getVocabSize() ?: -1
            val debugInfo = """
                Vocab Size: $vocabSize
                Input IDs: ${inputIds.size} [${inputIds.take(5).joinToString()},...]
                Output IDs: $outputIds
                Raw Output Length: ${outputIds.size}
            """.trimIndent()
            
            return "DEBUG_ERROR: Empty prediction\n$debugInfo\n\n" + extractiveSummary(text)
        }
        return formatSummary(decodedText)
    }


    private fun getArgmax(logits: Any?): Long {
        val batch = logits as Array<*>
        val seq = batch[0] as Array<*>
        val lastTokenLogits = seq[seq.size - 1] as FloatArray
        
        var maxIdx = 0
        var maxVal = Float.NEGATIVE_INFINITY
        for (i in lastTokenLogits.indices) {
            if (lastTokenLogits[i] > maxVal) {
                maxVal = lastTokenLogits[i]
                maxIdx = i
            }
        }
        return maxIdx.toLong()
    }

    private fun formatSummary(summary: String): String {
        val cleaned = summary.replace("<pad>", "").replace("</s>", "").trim()
        return "## Summary\n\n$cleaned\n\n---\n*Generated on-device with T5-small*"
    }

    private fun extractiveSummary(text: String): String {
        // Fallback simple extraction
        val sentences = text.split(Regex("(?<=[.!?])\\s+")).take(5)
        return "## Summary (Extractive)\n\n${sentences.joinToString(" ")}"
    }

    fun release() {
        encoderSession?.close()
        decoderSession?.close()
        ortEnv?.close()
    }
}

class SimpleTokenizer(tokenizerFile: File) {
    private val vocab = mutableMapOf<String, Long>()
    private val reverseVocab = mutableMapOf<Long, String>()
    
    init {
        try {
            val json = JSONObject(tokenizerFile.readText())
            val modelObj = json.optJSONObject("model")
            
            // Try as JSONArray (Common for T5/Unigram: [["token", score], ...])
            val vocabArray = modelObj?.optJSONArray("vocab")
            
            // Try as JSONObject (Common for BPE/WordPiece: {"token": id})
            val vocabObj = modelObj?.optJSONObject("vocab")
            
            if (vocabArray != null) {
                for (i in 0 until vocabArray.length()) {
                    val entry = vocabArray.optJSONArray(i)
                    if (entry != null && entry.length() > 0) {
                        val token = entry.getString(0)
                        val id = i.toLong()
                        vocab[token] = id
                        reverseVocab[id] = token
                    }
                }
            } else if (vocabObj != null) {
                vocabObj.keys().forEach { key ->
                    val id = vocabObj.getLong(key)
                    vocab[key] = id
                    reverseVocab[id] = key
                }
            } else {
                Log.e("Tokenizer", "No vocab found in tokenizer.json")
            }
        } catch (e: Exception) { 
            Log.e("Tokenizer", "Init failed: ${e.message}")
            e.printStackTrace()
        }
    }
    
    fun encode(text: String): List<Long> {
        val tokens = mutableListOf<Long>()
        // Replace spaces with sentencepiece underscore
        val normalized = text.replace(" ", "\u2581")
        
        var i = 0
        while (i < normalized.length) {
            var bestMatchId = 2L // UNK
            var bestMatchLen = 0
            
            // Greedy match: find longest token starting at i
            val maxLen = minOf(40, normalized.length - i)
            for (len in maxLen downTo 1) {
                val sub = normalized.substring(i, i + len)
                if (vocab.containsKey(sub)) {
                    bestMatchId = vocab[sub]!!
                    bestMatchLen = len
                    break
                }
            }
            
            if (bestMatchLen > 0) {
                tokens.add(bestMatchId)
                i += bestMatchLen
            } else {
                // Unknown char, fallback to UNK and skip 1 char
                tokens.add(2L)
                i++
            }
        }
        // Add EOS
        tokens.add(1L)
        return tokens
    }
    
    fun getVocabSize(): Int = vocab.size

    fun decode(ids: List<Long>): String {
        return ids.mapNotNull { reverseVocab[it] }.joinToString("")
            .replace("\u2581", " ").replace(" ", " ").trim()
    }
}
