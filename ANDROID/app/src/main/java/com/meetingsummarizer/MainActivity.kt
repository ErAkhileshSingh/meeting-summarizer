package com.meetingsummarizer

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.meetingsummarizer.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : AppCompatActivity() {
    
    private lateinit var binding: ActivityMainBinding
    private var whisperLib: WhisperLib? = null
    private var summarizer: T5Summarizer? = null
    private var modelDownloader: ModelDownloader? = null
    private var audioRecorder: AudioRecorder? = null
    private val recordingHandler = Handler(Looper.getMainLooper())
    private var recordingTimeSeconds = 0
    
    private val pickVideo = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let { processVideo(it) }
    }
    
    private val requestPermissions = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        if (permissions.all { it.value }) {
            pickVideo.launch("video/*")
        } else {
            Toast.makeText(this, "Permissions required", Toast.LENGTH_SHORT).show()
        }
    }
    
    private val requestRecordPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startRecording()
        } else {
            Toast.makeText(this, "Microphone permission required for recording", Toast.LENGTH_SHORT).show()
        }
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        
        audioRecorder = AudioRecorder(this)
        
        setupUI()
        initModels()
    }
    
    // Store current transcript and summary for saving
    private var currentTranscript: String = ""
    private var currentSummary: String = ""
    
    private fun setupUI() {
        binding.btnSelectVideo.setOnClickListener {
            checkPermissionsAndPick()
        }
        
        binding.btnRecord.setOnClickListener {
            toggleRecording()
        }
        
        // Save buttons
        binding.btnSaveTranscript.setOnClickListener {
            saveTextToFile(currentTranscript, "transcript")
        }
        
        binding.btnSaveSummary.setOnClickListener {
            saveTextToFile(currentSummary, "summary")
        }
    }
    
    private fun toggleRecording() {
        if (audioRecorder?.isRecording() == true) {
            stopRecording()
        } else {
            checkRecordPermissionAndStart()
        }
    }
    
    private fun checkRecordPermissionAndStart() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) 
            == PackageManager.PERMISSION_GRANTED) {
            startRecording()
        } else {
            requestRecordPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }
    
    private fun startRecording() {
        val started = audioRecorder?.startRecording { amplitude ->
            // Update UI with amplitude (could be used for visualization)
            runOnUiThread {
                binding.progressBar.progress = amplitude
            }
        } ?: false
        
        if (started) {
            binding.btnRecord.text = "⏹️ Stop Recording"
            binding.btnSelectVideo.isEnabled = false
            binding.progressBar.visibility = View.VISIBLE
            binding.tvStatus.text = "🎙️ Recording... 0:00"
            recordingTimeSeconds = 0
            startRecordingTimer()
            Toast.makeText(this, "Recording started", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "Failed to start recording", Toast.LENGTH_SHORT).show()
        }
    }
    
    private fun stopRecording() {
        stopRecordingTimer()
        binding.btnRecord.text = "🎤 Record"
        binding.btnSelectVideo.isEnabled = true
        binding.progressBar.visibility = View.GONE
        
        val audioFile = audioRecorder?.stopRecording()
        
        if (audioFile != null && audioFile.exists()) {
            Toast.makeText(this, "Recording saved!", Toast.LENGTH_SHORT).show()
            processAudioFile(audioFile)
        } else {
            binding.tvStatus.text = "Recording failed"
            Toast.makeText(this, "Failed to save recording", Toast.LENGTH_SHORT).show()
        }
    }
    
    private val recordingTimerRunnable = object : Runnable {
        override fun run() {
            recordingTimeSeconds++
            val minutes = recordingTimeSeconds / 60
            val seconds = recordingTimeSeconds % 60
            binding.tvStatus.text = "🎙️ Recording... $minutes:${String.format("%02d", seconds)}"
            recordingHandler.postDelayed(this, 1000)
        }
    }
    
    private fun startRecordingTimer() {
        recordingHandler.postDelayed(recordingTimerRunnable, 1000)
    }
    
    private fun stopRecordingTimer() {
        recordingHandler.removeCallbacks(recordingTimerRunnable)
    }
    
    private fun checkPermissionsAndPick() {
        val permissions = arrayOf(
            Manifest.permission.READ_MEDIA_VIDEO,
            Manifest.permission.READ_MEDIA_AUDIO
        )
        
        if (permissions.all { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }) {
            pickVideo.launch("video/*")
        } else {
            requestPermissions.launch(permissions)
        }
    }
    
    private fun initModels() {
        lifecycleScope.launch {
            showProgress("Checking models...")
            
            modelDownloader = ModelDownloader(this@MainActivity)
            
            // Download models if not present
            if (!modelDownloader!!.areModelsReady()) {
                showProgress("Downloading models (first time only)...")
                modelDownloader!!.downloadModels { progress ->
                    runOnUiThread {
                        binding.progressBar.progress = progress
                        binding.tvStatus.text = "Downloading: $progress%"
                    }
                }
            }
            
            // Load models on IO thread to prevent ANR
            withContext(Dispatchers.IO) {
                // Initialize whisper
                runOnUiThread { showProgress("Loading Whisper model...") }
                whisperLib = WhisperLib(this@MainActivity)
                whisperLib?.loadModel()
                
                // Initialize T5
                runOnUiThread { showProgress("Loading T5 summarizer...") }
                summarizer = T5Summarizer(this@MainActivity)
                summarizer?.loadModel()
            }
            
            hideProgress()
            binding.tvStatus.text = "Ready! Select a video to summarize."
        }
    }
    
    private fun processVideo(uri: Uri) {
        lifecycleScope.launch {
            try {
                showProgress("Extracting audio...")
                
                // All heavy operations on IO thread to prevent ANR
                val audioFile = withContext(Dispatchers.IO) {
                    // Copy video to temp file
                    val tempVideo = File(cacheDir, "temp_video.mp4")
                    contentResolver.openInputStream(uri)?.use { input ->
                        tempVideo.outputStream().use { output ->
                            input.copyTo(output)
                        }
                    }
                    
                    // Extract audio (heavy operation)
                    val audio = AudioProcessor.extractAudio(this@MainActivity, tempVideo)
                    
                    // Clean up temp video after extraction
                    tempVideo.delete()
                    
                    audio
                }
                binding.progressBar.progress = 20
                
                // Transcribe
                showProgress("Transcribing (this may take a while)...")
                val transcript = withContext(Dispatchers.Default) {
                    whisperLib?.transcribe(audioFile.absolutePath) ?: ""
                }
                binding.progressBar.progress = 60
                
                // Check if transcription worked
                if (transcript.isBlank() || transcript.startsWith("Error:")) {
                    binding.tvTranscript.text = "Transcription failed: $transcript"
                    binding.tvSummary.text = "Cannot summarize - no transcript available"
                    hideProgress()
                    binding.tvStatus.text = "Transcription failed"
                    audioFile.delete()
                    return@launch
                }
                
                // Show transcript and store for saving
                currentTranscript = transcript
                binding.tvTranscript.text = transcript
                binding.btnSaveTranscript.visibility = View.VISIBLE
                android.util.Log.d("MainActivity", "Transcript length: ${transcript.length} chars")
                
                // Summarize
                showProgress("Generating summary...")
                val summary = withContext(Dispatchers.Default) {
                    try {
                        // Ensure summarizer is available
                        val sum = summarizer ?: run {
                            android.util.Log.w("MainActivity", "Summarizer was null, creating new instance")
                            T5Summarizer(this@MainActivity).also { 
                                it.loadModel()
                                summarizer = it
                            }
                        }
                        sum.summarize(transcript)
                    } catch (e: Exception) {
                        android.util.Log.e("MainActivity", "Summarization error: ${e.message}", e)
                        "## Summary\n\nError generating summary: ${e.message}\n\nTranscript available above."
                    }
                }
                binding.progressBar.progress = 100
                
                // Show summary and store for saving
                currentSummary = summary
                binding.tvSummary.text = summary
                binding.btnSaveSummary.visibility = View.VISIBLE
                android.util.Log.d("MainActivity", "Summary generated: ${summary.length} chars")
                
                hideProgress()
                binding.tvStatus.text = "Complete!"
                
                // Cleanup (tempVideo already deleted in coroutine)
                audioFile.delete()
                
            } catch (e: Exception) {
                hideProgress()
                binding.tvStatus.text = "Error: ${e.message}"
                android.util.Log.e("MainActivity", "processVideo error", e)
                e.printStackTrace()
            }
        }
    }
    
    private fun showProgress(message: String) {
        binding.progressBar.visibility = View.VISIBLE
        binding.tvStatus.text = message
    }
    
    private fun hideProgress() {
        binding.progressBar.visibility = View.GONE
    }
    
    /**
     * Process a recorded audio file (already in 16kHz WAV format)
     */
    private fun processAudioFile(audioFile: File) {
        lifecycleScope.launch {
            try {
                showProgress("Transcribing recording...")
                binding.progressBar.progress = 30
                
                // Transcribe on Default (CPU) thread
                val transcript = withContext(Dispatchers.Default) {
                    whisperLib?.transcribe(audioFile.absolutePath) ?: ""
                }
                binding.progressBar.progress = 60
                
                // Check if transcription worked
                if (transcript.isBlank() || transcript.startsWith("Error:")) {
                    binding.tvTranscript.text = "Transcription failed: $transcript"
                    binding.tvSummary.text = "Cannot summarize - no transcript available"
                    hideProgress()
                    binding.tvStatus.text = "Transcription failed"
                    return@launch
                }
                
                // Show transcript and store for saving
                currentTranscript = transcript
                binding.tvTranscript.text = transcript
                binding.btnSaveTranscript.visibility = View.VISIBLE
                android.util.Log.d("MainActivity", "Transcript from recording: ${transcript.length} chars")
                
                // Summarize
                showProgress("Generating summary...")
                val summary = withContext(Dispatchers.Default) {
                    try {
                        // Ensure summarizer is available
                        val sum = summarizer ?: run {
                            android.util.Log.w("MainActivity", "Summarizer was null, creating new instance")
                            T5Summarizer(this@MainActivity).also { 
                                it.loadModel()
                                summarizer = it
                            }
                        }
                        sum.summarize(transcript)
                    } catch (e: Exception) {
                        android.util.Log.e("MainActivity", "Summarization error: ${e.message}", e)
                        "## Summary\n\nError generating summary: ${e.message}\n\nTranscript available above."
                    }
                }
                binding.progressBar.progress = 100
                
                // Show summary and store for saving
                currentSummary = summary
                binding.tvSummary.text = summary
                binding.btnSaveSummary.visibility = View.VISIBLE
                android.util.Log.d("MainActivity", "Summary generated: ${summary.length} chars")
                
                hideProgress()
                binding.tvStatus.text = "Complete!"
                
                // Keep the recording file for later reference
                Toast.makeText(this@MainActivity, 
                    "Recording saved: ${audioFile.name}", Toast.LENGTH_LONG).show()
                
            } catch (e: Exception) {
                hideProgress()
                binding.tvStatus.text = "Error: ${e.message}"
                android.util.Log.e("MainActivity", "processAudioFile error", e)
                e.printStackTrace()
            }
        }
    }
    
    /**
     * Save text content to a file in Downloads folder
     */
    private fun saveTextToFile(content: String, type: String) {
        if (content.isBlank()) {
            Toast.makeText(this, "Nothing to save", Toast.LENGTH_SHORT).show()
            return
        }
        
        lifecycleScope.launch {
            try {
                val timestamp = java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.getDefault())
                    .format(java.util.Date())
                val filename = "meeting_${type}_$timestamp.txt"
                
                // Save to app's files directory (always accessible)
                val outputDir = File(filesDir, "saved_${type}s")
                outputDir.mkdirs()
                val outputFile = File(outputDir, filename)
                
                withContext(Dispatchers.IO) {
                    outputFile.writeText(content)
                }
                
                Toast.makeText(
                    this@MainActivity, 
                    "✅ Saved to: ${outputFile.name}\n(${filesDir.absolutePath}/saved_${type}s/)", 
                    Toast.LENGTH_LONG
                ).show()
                
                android.util.Log.d("MainActivity", "Saved $type to: ${outputFile.absolutePath}")
                
                // Also try to copy to Downloads via share intent
                shareFile(outputFile, type)
                
            } catch (e: Exception) {
                android.util.Log.e("MainActivity", "Failed to save $type: ${e.message}", e)
                Toast.makeText(this@MainActivity, "Failed to save: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }
    
    /**
     * Share a file using system share sheet
     */
    private fun shareFile(file: File, type: String) {
        try {
            val uri = androidx.core.content.FileProvider.getUriForFile(
                this,
                "${packageName}.fileprovider",
                file
            )
            
            val shareIntent = android.content.Intent().apply {
                action = android.content.Intent.ACTION_SEND
                putExtra(android.content.Intent.EXTRA_STREAM, uri)
                setType("text/plain")
                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            
            startActivity(android.content.Intent.createChooser(shareIntent, "Share $type"))
        } catch (e: Exception) {
            android.util.Log.e("MainActivity", "Share failed: ${e.message}")
            // Share failed but file was still saved locally
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        // Cancel any ongoing recording
        audioRecorder?.cancelRecording()
        stopRecordingTimer()
        whisperLib?.release()
        summarizer?.release()
    }
}
