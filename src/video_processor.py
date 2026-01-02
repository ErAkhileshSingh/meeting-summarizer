"""
Video Processor Module
Extracts audio from video files using FFmpeg.
"""

import subprocess
import shutil
from pathlib import Path
import os


class VideoProcessor:
    """Extracts audio from video files using FFmpeg."""
    
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
    
    def __init__(self, temp_dir: str = None):
        """
        Initialize the video processor.
        
        Args:
            temp_dir: Directory for temporary audio files
        """
        project_root = Path(__file__).parent.parent
        self.temp_dir = Path(temp_dir) if temp_dir else project_root / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Find FFmpeg
        self.ffmpeg_path = self._find_ffmpeg()
    
    def _find_ffmpeg(self) -> str:
        """Find FFmpeg executable."""
        # Check if ffmpeg is in PATH
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        
        # Common Windows locations
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        
        for path in common_paths:
            if Path(path).exists():
                return path
        
        return None
    
    def is_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available."""
        return self.ffmpeg_path is not None
    
    def get_ffmpeg_version(self) -> str:
        """Get FFmpeg version string."""
        if not self.is_ffmpeg_available():
            return "FFmpeg not found"
        
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            first_line = result.stdout.split('\n')[0]
            return first_line
        except Exception as e:
            return f"Error: {e}"
    
    def is_supported_format(self, video_path: str) -> bool:
        """Check if the video format is supported."""
        ext = Path(video_path).suffix.lower()
        return ext in self.SUPPORTED_FORMATS
    
    def extract_audio(self, video_path: str, progress_callback=None) -> str:
        """
        Extract audio from video file.
        
        Args:
            video_path: Path to the video file
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to the extracted audio file (WAV format)
            
        Raises:
            RuntimeError: If FFmpeg is not available or extraction fails
        """
        if not self.is_ffmpeg_available():
            raise RuntimeError(
                "FFmpeg not found! Please install FFmpeg and add it to your PATH.\n"
                "Download from: https://ffmpeg.org/download.html"
            )
        
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not self.is_supported_format(str(video_path)):
            raise ValueError(
                f"Unsupported video format: {video_path.suffix}\n"
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            )
        
        # Output audio file path
        audio_filename = f"{video_path.stem}_audio.wav"
        audio_path = self.temp_dir / audio_filename
        
        if progress_callback:
            progress_callback("Extracting audio from video...")
        
        # FFmpeg command: extract audio, convert to 16kHz mono WAV
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),        # Input video
            "-vn",                         # No video
            "-acodec", "pcm_s16le",       # PCM 16-bit encoding
            "-ar", "16000",               # 16kHz sample rate (optimal for Whisper)
            "-ac", "1",                   # Mono channel
            "-y",                         # Overwrite output
            str(audio_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout for long videos
            )
            
            if result.returncode != 0:
                error_msg = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                raise RuntimeError(f"FFmpeg error:\n{error_msg}")
            
            if not audio_path.exists():
                raise RuntimeError("Audio extraction failed - output file not created")
            
            if progress_callback:
                size_mb = audio_path.stat().st_size / (1024 * 1024)
                progress_callback(f"Audio extracted: {size_mb:.1f} MB")
            
            return str(audio_path)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Audio extraction timed out (>10 minutes)")
    
    def get_video_duration(self, video_path: str) -> float:
        """
        Get video duration in seconds.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Duration in seconds
        """
        if not self.is_ffmpeg_available():
            return 0.0
        
        # Use ffprobe (comes with FFmpeg)
        ffprobe = self.ffmpeg_path.replace("ffmpeg", "ffprobe")
        
        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip())
        except:
            return 0.0
    
    def cleanup_temp_files(self):
        """Remove temporary audio files."""
        for file in self.temp_dir.glob("*_audio.wav"):
            try:
                file.unlink()
            except:
                pass
    
    def chunk_audio(self, audio_path: str, chunk_duration: int = 30, progress_callback=None) -> list:
        """
        Split audio into chunks for parallel processing.
        
        Args:
            audio_path: Path to the audio file
            chunk_duration: Duration of each chunk in seconds (default: 30)
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of paths to chunk files
        """
        if not self.is_ffmpeg_available():
            raise RuntimeError("FFmpeg not found!")
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Create chunks directory
        chunks_dir = self.temp_dir / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        # Clear existing chunks
        for f in chunks_dir.glob("*.wav"):
            f.unlink()
        
        if progress_callback:
            progress_callback("Splitting audio into chunks...")
        
        # FFmpeg command to segment audio
        output_pattern = str(chunks_dir / "chunk_%03d.wav")
        
        cmd = [
            self.ffmpeg_path,
            "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(chunk_duration),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            output_pattern
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                error_msg = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                raise RuntimeError(f"FFmpeg chunking error:\n{error_msg}")
            
            # Get sorted list of chunk files
            chunk_files = sorted(chunks_dir.glob("chunk_*.wav"))
            
            if not chunk_files:
                raise RuntimeError("No audio chunks created")
            
            if progress_callback:
                progress_callback(f"Created {len(chunk_files)} audio chunks ({chunk_duration}s each)")
            
            return [str(f) for f in chunk_files]
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Audio chunking timed out")
    
    def cleanup_chunks(self):
        """Remove temporary chunk files."""
        chunks_dir = self.temp_dir / "chunks"
        if chunks_dir.exists():
            for file in chunks_dir.glob("*.wav"):
                try:
                    file.unlink()
                except:
                    pass
            try:
                chunks_dir.rmdir()
            except:
                pass


def test_video_processor():
    """Test the video processor module."""
    processor = VideoProcessor()
    
    print("Video Processor Test")
    print("=" * 40)
    print(f"FFmpeg available: {processor.is_ffmpeg_available()}")
    print(f"FFmpeg path: {processor.ffmpeg_path}")
    print(f"FFmpeg version: {processor.get_ffmpeg_version()}")
    print(f"Temp directory: {processor.temp_dir}")
    print(f"Supported formats: {processor.SUPPORTED_FORMATS}")


if __name__ == "__main__":
    test_video_processor()
