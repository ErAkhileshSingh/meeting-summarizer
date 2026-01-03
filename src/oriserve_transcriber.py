"""
Oriserve Hindi/Hinglish Transcriber Module
Uses Oriserve/Whisper-Hindi2Hinglish-Apex for accurate Hindi/Hinglish transcription.
Optimized for Indian accents and code-mixed speech.
"""

import os
from pathlib import Path
import warnings
import torch

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Set cache directory
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "oriserve-whisper"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class OriserveTranscriber:
    """Hindi/Hinglish transcription using Oriserve/Whisper-Hindi2Hinglish-Apex."""
    
    MODEL_ID = "Oriserve/Whisper-Hindi2Hinglish-Apex"
    
    def __init__(self):
        """Initialize the Oriserve transcriber."""
        self.model = None
        self.processor = None
        self.pipe = None
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model_dir = str(MODELS_DIR)
    
    def load_model(self, progress_callback=None):
        """
        Load the Oriserve Whisper model.
        
        Args:
            progress_callback: Optional callback for progress updates
        """
        if self.pipe is not None:
            return
        
        if progress_callback:
            progress_callback(f"Loading Oriserve Hindi/Hinglish model...")
            progress_callback(f"This may take a few minutes on first run (downloading ~3GB)...")
        
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
            
            # Set cache directory
            os.environ["HF_HOME"] = self.model_dir
            os.environ["TRANSFORMERS_CACHE"] = self.model_dir
            
            if progress_callback:
                progress_callback("Loading model weights...")
            
            # Load the speech-to-text model
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.MODEL_ID,
                torch_dtype=self.torch_dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True,
                cache_dir=self.model_dir
            )
            self.model.to(self.device)
            
            if progress_callback:
                progress_callback("Loading processor...")
            
            # Load the processor
            self.processor = AutoProcessor.from_pretrained(
                self.MODEL_ID,
                cache_dir=self.model_dir
            )
            
            if progress_callback:
                progress_callback("Creating transcription pipeline...")
            
            # Create speech recognition pipeline
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=self.model,
                tokenizer=self.processor.tokenizer,
                feature_extractor=self.processor.feature_extractor,
                torch_dtype=self.torch_dtype,
                device=self.device,
                generate_kwargs={
                    "task": "transcribe",
                    "language": "en"  # Outputs Hinglish (Roman script)
                }
            )
            
            if progress_callback:
                progress_callback("Oriserve model loaded successfully!")
                
        except ImportError as e:
            raise ImportError(
                f"Required packages not installed.\n"
                f"Install with: pip install transformers torch safetensors\n"
                f"Error: {e}"
            )
    
    def transcribe_chunk(self, chunk_path: str) -> dict:
        """
        Transcribe a single audio chunk.
        
        Args:
            chunk_path: Path to the audio chunk file
            
        Returns:
            Dictionary with text and segments
        """
        if self.pipe is None:
            self.load_model()
        
        # Run inference
        result = self.pipe(chunk_path, return_timestamps=True)
        
        # Extract text
        text = result.get("text", "").strip()
        
        # Extract segments if available
        segments = []
        if "chunks" in result:
            for chunk in result["chunks"]:
                timestamp = chunk.get("timestamp", (0, 0))
                segments.append({
                    "start": timestamp[0] if timestamp[0] else 0,
                    "end": timestamp[1] if timestamp[1] else 0,
                    "text": chunk.get("text", "").strip()
                })
        else:
            # Single segment fallback
            segments.append({
                "start": 0,
                "end": 0,
                "text": text
            })
        
        return {
            "text": text,
            "segments": segments,
            "language": "hi-en"  # Hindi-English (Hinglish)
        }
    
    def transcribe_parallel(self, chunk_files: list, progress_callback=None) -> dict:
        """
        Transcribe audio chunks sequentially (Oriserve doesn't benefit from parallel).
        
        Note: Unlike faster-whisper, transformers pipeline already optimizes internally,
        so we process sequentially to avoid memory issues.
        
        Args:
            chunk_files: List of paths to audio chunk files
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with combined text and segments
        """
        if self.pipe is None:
            self.load_model(progress_callback)
        
        if progress_callback:
            progress_callback(f"Transcribing {len(chunk_files)} chunks (Hindi/Hinglish mode)...")
        
        all_results = []
        
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
        
        full_transcript = " ".join(combined_text)
        
        if progress_callback:
            progress_callback(f"Transcription complete: {len(full_transcript)} characters")
        
        return {
            "text": full_transcript,
            "segments": combined_segments,
            "language": "hi-en",
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
        if self.pipe is None:
            self.load_model(progress_callback)
        
        if progress_callback:
            progress_callback("Transcribing audio (Hindi/Hinglish mode)...")
        
        result = self.transcribe_chunk(audio_path)
        
        if progress_callback:
            progress_callback(f"Transcription complete: {len(result['text'])} characters")
        
        return {
            "text": result["text"],
            "segments": result["segments"],
            "language": "hi-en",
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
        if seconds is None:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def get_model_info(self) -> dict:
        """Get information about the current model."""
        return {
            "model_id": self.MODEL_ID,
            "device": self.device,
            "dtype": str(self.torch_dtype),
            "model_dir": self.model_dir,
            "loaded": self.pipe is not None,
            "features": ["Hindi", "Hinglish", "Indian English", "Noise Robust"]
        }


def test_oriserve_transcriber():
    """Test the Oriserve transcriber module."""
    print("Oriserve Transcriber Test")
    print("=" * 40)
    
    transcriber = OriserveTranscriber()
    info = transcriber.get_model_info()
    
    print(f"Model ID: {info['model_id']}")
    print(f"Device: {info['device']}")
    print(f"Data Type: {info['dtype']}")
    print(f"Model directory: {info['model_dir']}")
    print(f"Model loaded: {info['loaded']}")
    print(f"Features: {', '.join(info['features'])}")


if __name__ == "__main__":
    test_oriserve_transcriber()
