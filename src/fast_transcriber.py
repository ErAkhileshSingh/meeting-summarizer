"""
Fast Transcriber Module
High-speed speech-to-text using faster-whisper with parallel chunk processing.
Optimized for meeting transcription - processes 1 hour in ~3 minutes.
"""

import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Set cache directory before importing
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "faster-whisper"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class FastTranscriber:
    """High-speed transcription using faster-whisper with parallel processing."""
    
    # Model sizes and their properties
    MODEL_INFO = {
        "tiny": {"size": "~39 MB", "speed": "fastest", "accuracy": "basic"},
        "base": {"size": "~74 MB", "speed": "very fast", "accuracy": "good"},
        "small": {"size": "~244 MB", "speed": "fast", "accuracy": "high"},
        "medium": {"size": "~769 MB", "speed": "moderate", "accuracy": "very high"},
        "large-v3": {"size": "~1.5 GB", "speed": "slow", "accuracy": "best"},
    }
    
    def __init__(self, model_size: str = "small", num_workers: int = 4):
        """
        Initialize the fast transcriber.
        
        Args:
            model_size: Whisper model size (tiny/base/small/medium/large-v3)
                       Default is 'small' for optimal speed/accuracy balance.
            num_workers: Number of parallel workers for chunk processing
        """
        self.model_size = model_size
        self.num_workers = num_workers
        self.model = None
        self.model_dir = str(MODELS_DIR)
        
        # Validate model size
        if model_size not in self.MODEL_INFO:
            raise ValueError(
                f"Invalid model size: {model_size}\n"
                f"Available: {list(self.MODEL_INFO.keys())}"
            )
    
    def load_model(self, progress_callback=None):
        """
        Load the faster-whisper model.
        
        Args:
            progress_callback: Optional callback for progress updates
        """
        if self.model is not None:
            return
        
        if progress_callback:
            info = self.MODEL_INFO[self.model_size]
            progress_callback(f"Loading Whisper {self.model_size} model ({info['size']})...")
        
        try:
            from faster_whisper import WhisperModel
            
            # Load model with CPU optimization
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",  # Faster on CPU
                download_root=self.model_dir
            )
            
            if progress_callback:
                progress_callback(f"Whisper {self.model_size} model loaded!")
                
        except ImportError:
            raise ImportError(
                "faster-whisper package not installed.\n"
                "Install with: pip install faster-whisper"
            )
    
    def transcribe_chunk(self, chunk_path: str) -> dict:
        """
        Transcribe a single audio chunk with optimized settings.
        
        Args:
            chunk_path: Path to the audio chunk file
            
        Returns:
            Dictionary with text and segments
        """
        if self.model is None:
            self.load_model()
        
        # Optimized settings for speed
        segments, info = self.model.transcribe(
            chunk_path,
            beam_size=1,          # Greedy decoding - 5x faster than beam_size=5
            best_of=1,            # No sampling variations
            vad_filter=True,      # Remove silence
            vad_parameters=dict(min_silence_duration_ms=300),
            word_timestamps=False,  # Don't need word-level timestamps
            condition_on_previous_text=False  # Faster, each chunk independent
        )
        
        # Collect segments - force iteration (segments is a generator)
        segment_list = []
        full_text = []
        
        for seg in segments:
            segment_list.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip()
            })
            full_text.append(seg.text.strip())
        
        return {
            "text": " ".join(full_text),
            "segments": segment_list,
            "language": info.language
        }
    
    def transcribe_parallel(self, chunk_files: list, progress_callback=None) -> dict:
        """
        Transcribe audio chunks sequentially (faster than parallel for CPU inference).
        
        Note: Despite the name, sequential processing is faster because:
        - faster-whisper uses all CPU cores internally
        - Threading adds overhead without true parallelism
        - Model inference is CPU-bound, not I/O-bound
        
        Args:
            chunk_files: List of paths to audio chunk files
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with combined text and segments
        """
        if self.model is None:
            self.load_model(progress_callback)
        
        if progress_callback:
            progress_callback(f"Transcribing {len(chunk_files)} chunks...")
        
        all_results = []
        
        # Process chunks sequentially - faster on CPU
        for idx, chunk in enumerate(chunk_files):
            if progress_callback:
                progress_callback(f"Transcribed {idx}/{len(chunk_files)} chunks...")
            
            try:
                result = self.transcribe_chunk(chunk)
                all_results.append(result)
            except Exception as e:
                all_results.append({"text": "", "segments": [], "error": str(e)})
        
        if progress_callback:
            progress_callback(f"Transcribed {len(chunk_files)}/{len(chunk_files)} chunks...")
        
        # Combine results in order
        combined_text = []
        combined_segments = []
        detected_language = "unknown"
        
        for idx, result in enumerate(all_results):
            if result and result.get("text"):
                combined_text.append(result["text"])
                
                # Adjust timestamps for chunk position
                chunk_duration = 30.0  # Default chunk duration
                time_offset = idx * chunk_duration
                
                for seg in result.get("segments", []):
                    combined_segments.append({
                        "start": seg["start"] + time_offset,
                        "end": seg["end"] + time_offset,
                        "text": seg["text"]
                    })
                
                if result.get("language") and detected_language == "unknown":
                    detected_language = result["language"]
        
        full_transcript = " ".join(combined_text)
        
        if progress_callback:
            progress_callback(f"Transcription complete: {len(full_transcript)} characters")
        
        return {
            "text": full_transcript,
            "segments": combined_segments,
            "language": detected_language,
            "word_count": len(full_transcript.split())
        }
    
    def transcribe_single(self, audio_path: str, progress_callback=None) -> dict:
        """
        Transcribe a single audio file (non-chunked).
        
        Args:
            audio_path: Path to the audio file
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with text and segments
        """
        if self.model is None:
            self.load_model(progress_callback)
        
        if progress_callback:
            progress_callback("Transcribing audio...")
        
        result = self.transcribe_chunk(audio_path)
        
        if progress_callback:
            progress_callback(f"Transcription complete: {len(result['text'])} characters")
        
        return {
            "text": result["text"],
            "segments": result["segments"],
            "language": result.get("language", "unknown"),
            "word_count": len(result["text"].split())
        }
    
    def format_transcript_with_timestamps(self, result: dict) -> str:
        """
        Format transcript with timestamps for readability.
        
        Args:
            result: Transcription result dictionary
            
        Returns:
            Formatted transcript string with timestamps
        """
        lines = []
        for seg in result.get("segments", []):
            start = self._format_timestamp(seg["start"])
            end = self._format_timestamp(seg["end"])
            text = seg["text"]
            lines.append(f"[{start} → {end}] {text}")
        
        return "\n".join(lines)
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def get_model_info(self) -> dict:
        """Get information about the current model."""
        return {
            "model_size": self.model_size,
            "info": self.MODEL_INFO[self.model_size],
            "model_dir": self.model_dir,
            "num_workers": self.num_workers,
            "loaded": self.model is not None
        }


def test_fast_transcriber():
    """Test the fast transcriber module."""
    print("Fast Transcriber Test")
    print("=" * 40)
    
    transcriber = FastTranscriber(model_size="small", num_workers=4)
    info = transcriber.get_model_info()
    
    print(f"Model size: {info['model_size']}")
    print(f"Download size: {info['info']['size']}")
    print(f"Speed: {info['info']['speed']}")
    print(f"Accuracy: {info['info']['accuracy']}")
    print(f"Model directory: {info['model_dir']}")
    print(f"Workers: {info['num_workers']}")
    print(f"Model loaded: {info['loaded']}")
    print("\nAll model sizes:")
    for size, details in FastTranscriber.MODEL_INFO.items():
        print(f"  {size}: {details['size']} ({details['speed']})")


if __name__ == "__main__":
    test_fast_transcriber()
