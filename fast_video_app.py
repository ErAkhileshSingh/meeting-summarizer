"""
Fast Video Summary App
======================
Optimized pipeline: 1-hour meeting → 5-minute processing
Uses chunked audio + parallel transcription + hierarchical summarization.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import queue
import sys
import os
from pathlib import Path
from datetime import datetime
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


class FastVideoSummaryApp:
    """Optimized Video to Summary GUI Application."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("⚡ Fast Video Summary Generator")
        self.root.geometry("950x800")
        self.root.minsize(850, 700)
        
        # Theme colors (dark mode)
        self.bg_color = "#1a1a2e"
        self.fg_color = "#eaeaea"
        self.accent_color = "#0f3460"
        self.button_color = "#16213e"
        self.highlight_color = "#e94560"
        self.success_color = "#4ecca3"
        self.text_bg = "#16213e"
        self.warning_color = "#ffa502"
        
        self.root.configure(bg=self.bg_color)
        
        # Message queue for thread communication
        self.message_queue = queue.Queue()
        
        # State
        self.processing = False
        self.stop_requested = False
        self.current_video = None
        self.current_transcript = None
        self.current_summary = None
        self.start_time = None
        
        # Build UI
        self._create_ui()
        
        # Start message processing
        self._process_messages()
    
    def _create_ui(self):
        """Create the user interface."""
        
        # Main container with padding
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=25, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== Header =====
        header_frame = tk.Frame(main_frame, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = tk.Label(
            header_frame,
            text="⚡ Fast Video Summary Generator",
            font=("Segoe UI", 24, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="1-hour video → 5-minute processing • Chunked + Parallel Transcription",
            font=("Segoe UI", 11),
            bg=self.bg_color,
            fg=self.success_color
        )
        subtitle_label.pack()
        
        # ===== Settings Frame =====
        settings_frame = tk.Frame(main_frame, bg=self.accent_color, padx=15, pady=10)
        settings_frame.pack(fill=tk.X, pady=10)
        
        # Model selection
        tk.Label(
            settings_frame,
            text="Model:",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.model_var = tk.StringVar(value="small")
        model_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.model_var,
            values=["tiny", "base", "small", "medium"],
            state="readonly",
            width=10
        )
        model_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # Workers selection
        tk.Label(
            settings_frame,
            text="Workers:",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.workers_var = tk.StringVar(value="4")
        workers_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.workers_var,
            values=["2", "4", "6", "8"],
            state="readonly",
            width=5
        )
        workers_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # Chunk duration
        tk.Label(
            settings_frame,
            text="Chunk (sec):",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.chunk_var = tk.StringVar(value="30")
        chunk_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.chunk_var,
            values=["15", "30", "45", "60"],
            state="readonly",
            width=5
        )
        chunk_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # Summary word limit
        tk.Label(
            settings_frame,
            text="Summary Words:",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.summary_words_var = tk.StringVar(value="800")
        summary_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.summary_words_var,
            values=["400", "600", "800", "1000", "1200"],
            state="readonly",
            width=6
        )
        summary_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # Transcriber selection (NEW)
        tk.Label(
            settings_frame,
            text="Transcriber:",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.transcriber_var = tk.StringVar(value="faster-whisper")
        transcriber_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.transcriber_var,
            values=["faster-whisper", "oriserve-hindi"],
            state="readonly",
            width=14
        )
        transcriber_combo.pack(side=tk.LEFT)
        
        # Speed indicator
        self.speed_label = tk.Label(
            settings_frame,
            text="⚡ Fast mode",
            font=("Segoe UI", 10),
            bg=self.accent_color,
            fg=self.success_color
        )
        self.speed_label.pack(side=tk.RIGHT)
        
        # ===== Video Selection =====
        video_frame = tk.Frame(main_frame, bg=self.bg_color)
        video_frame.pack(fill=tk.X, pady=15)
        
        self.select_btn = tk.Button(
            video_frame,
            text="📁 Select Video File",
            command=self._select_video,
            bg=self.highlight_color,
            fg="white",
            font=("Segoe UI", 13, "bold"),
            width=20,
            height=2,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#c73e54"
        )
        self.select_btn.pack(side=tk.LEFT)
        
        self.file_label = tk.Label(
            video_frame,
            text="No file selected",
            font=("Segoe UI", 11),
            bg=self.bg_color,
            fg="#888888",
            anchor=tk.W
        )
        self.file_label.pack(side=tk.LEFT, padx=20, fill=tk.X, expand=True)
        
        # ===== Button Row =====
        button_row = tk.Frame(main_frame, bg=self.bg_color)
        button_row.pack(pady=15)
        
        self.process_btn = tk.Button(
            button_row,
            text="🚀 Generate Transcript & Summary (FAST)",
            command=self._start_processing,
            bg=self.success_color,
            fg="#1a1a2e",
            font=("Segoe UI", 14, "bold"),
            width=35,
            height=2,
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED,
            activebackground="#3db890"
        )
        self.process_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = tk.Button(
            button_row,
            text="⏹️ Stop",
            command=self._stop_processing,
            bg=self.highlight_color,
            fg="white",
            font=("Segoe UI", 14, "bold"),
            width=10,
            height=2,
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED,
            activebackground="#c73e54"
        )
        self.stop_btn.pack(side=tk.LEFT)
        
        # ===== Progress Section =====
        progress_frame = tk.Frame(main_frame, bg=self.bg_color)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            length=600
        )
        self.progress.pack()
        
        # Status with timer
        status_row = tk.Frame(progress_frame, bg=self.bg_color)
        status_row.pack(fill=tk.X, pady=5)
        
        self.status_label = tk.Label(
            status_row,
            text="Ready",
            font=("Segoe UI", 11),
            bg=self.bg_color,
            fg=self.success_color
        )
        self.status_label.pack(side=tk.LEFT)
        
        self.timer_label = tk.Label(
            status_row,
            text="",
            font=("Segoe UI", 11, "bold"),
            bg=self.bg_color,
            fg=self.warning_color
        )
        self.timer_label.pack(side=tk.RIGHT)
        
        # ===== Transcript Section =====
        transcript_header = tk.Frame(main_frame, bg=self.bg_color)
        transcript_header.pack(fill=tk.X, pady=(15, 5))
        
        tk.Label(
            transcript_header,
            text="📝 Transcript",
            font=("Segoe UI", 13, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        self.save_transcript_btn = tk.Button(
            transcript_header,
            text="💾 Save",
            command=self._save_transcript,
            bg=self.button_color,
            fg=self.fg_color,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.save_transcript_btn.pack(side=tk.RIGHT)
        
        self.transcript_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.text_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            height=10,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.transcript_text.pack(fill=tk.BOTH, expand=True)
        
        # ===== Summary Section =====
        summary_header = tk.Frame(main_frame, bg=self.bg_color)
        summary_header.pack(fill=tk.X, pady=(15, 5))
        
        tk.Label(
            summary_header,
            text="📋 Summary",
            font=("Segoe UI", 13, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        self.save_summary_btn = tk.Button(
            summary_header,
            text="💾 Save",
            command=self._save_summary,
            bg=self.button_color,
            fg=self.fg_color,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.save_summary_btn.pack(side=tk.RIGHT)
        
        self.summary_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.text_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            height=8,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)
        
        # ===== Footer =====
        footer = tk.Label(
            main_frame,
            text="faster-whisper (Fast) | Oriserve Hindi/Hinglish (Accurate) • BART-large-CNN for summarization",
            font=("Segoe UI", 9),
            bg=self.bg_color,
            fg="#666666"
        )
        footer.pack(pady=(10, 0))
    
    def _select_video(self):
        """Open file dialog to select a video file."""
        filetypes = [
            ("Video files", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv *.m4v"),
            ("MP4 files", "*.mp4"),
            ("All files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=filetypes,
            initialdir=str(Path.home() / "Videos")
        )
        
        if filepath:
            self.current_video = filepath
            filename = Path(filepath).name
            
            # Truncate long filenames
            if len(filename) > 50:
                filename = filename[:47] + "..."
            
            self.file_label.configure(text=f"📹 {filename}", fg=self.fg_color)
            self.process_btn.configure(state=tk.NORMAL)
    
    def _start_processing(self):
        """Start the optimized video processing pipeline."""
        if not self.current_video:
            return
        
        self.processing = True
        self.stop_requested = False
        self.start_time = time.time()
        
        # Disable buttons during processing
        self.select_btn.configure(state=tk.DISABLED)
        self.process_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)  # Enable stop button
        self.save_transcript_btn.configure(state=tk.DISABLED)
        self.save_summary_btn.configure(state=tk.DISABLED)
        
        # Clear previous results
        self.transcript_text.delete(1.0, tk.END)
        self.summary_text.delete(1.0, tk.END)
        
        # Reset progress
        self.progress["value"] = 0
        
        # Get settings
        model_size = self.model_var.get()
        num_workers = int(self.workers_var.get())
        chunk_duration = int(self.chunk_var.get())
        summary_words = int(self.summary_words_var.get())
        transcriber_type = self.transcriber_var.get()  # NEW: Get selected transcriber
        
        # Process in background thread
        thread = threading.Thread(
            target=self._process_video_thread,
            args=(self.current_video, model_size, num_workers, chunk_duration, summary_words, transcriber_type),
            daemon=True
        )
        thread.start()
        
        # Start timer update
        self._update_timer()
    
    def _stop_processing(self):
        """Request stop of the current processing."""
        if self.processing:
            self.stop_requested = True
            self.status_label.configure(text="⏹️ Stopping... please wait", fg=self.warning_color)
            self.stop_btn.configure(state=tk.DISABLED)
    
    def _update_timer(self):
        """Update the elapsed time display."""
        if self.processing and self.start_time:
            elapsed = time.time() - self.start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            self.timer_label.configure(text=f"⏱️ {mins:02d}:{secs:02d}")
            self.root.after(1000, self._update_timer)
    
    def _process_video_thread(self, video_path: str, model_size: str, num_workers: int, chunk_duration: int, summary_words: int = 800, transcriber_type: str = "faster-whisper"):
        """Process video with optimized pipeline."""
        try:
            from src.video_processor import VideoProcessor
            from src.summarizer import Summarizer
            
            # Check for stop request helper
            def check_stop():
                if self.stop_requested:
                    raise InterruptedError("Processing stopped by user")
            
            # Step 1: Extract audio (5%)
            self.message_queue.put(("status", "Step 1/5: Extracting audio..."))
            self.message_queue.put(("progress", 2))
            check_stop()
            
            processor = VideoProcessor()
            
            if not processor.is_ffmpeg_available():
                raise RuntimeError(
                    "FFmpeg not found!\n\n"
                    "Please install FFmpeg and add it to your PATH.\n"
                    "Download from: https://ffmpeg.org/download.html"
                )
            
            audio_path = processor.extract_audio(
                video_path,
                progress_callback=lambda msg: self.message_queue.put(("status", f"Step 1/5: {msg}"))
            )
            self.message_queue.put(("progress", 5))
            check_stop()
            
            # Step 2: Chunk audio (10%)
            self.message_queue.put(("status", f"Step 2/5: Chunking audio ({chunk_duration}s segments)..."))
            chunk_files = processor.chunk_audio(
                audio_path,
                chunk_duration=chunk_duration,
                progress_callback=lambda msg: self.message_queue.put(("status", f"Step 2/5: {msg}"))
            )
            self.message_queue.put(("progress", 10))
            check_stop()
            
            # Step 3: Load transcriber (15%) - CONDITIONAL BASED ON SELECTION
            if transcriber_type == "oriserve-hindi":
                from src.oriserve_transcriber import OriserveTranscriber
                self.message_queue.put(("status", "Step 3/5: Loading Oriserve Hindi/Hinglish model..."))
                transcriber = OriserveTranscriber()
            else:
                from src.fast_transcriber import FastTranscriber
                self.message_queue.put(("status", f"Step 3/5: Loading Whisper {model_size} model..."))
                transcriber = FastTranscriber(model_size=model_size, num_workers=num_workers)
            
            transcriber.load_model(
                progress_callback=lambda msg: self.message_queue.put(("status", f"Step 3/5: {msg}"))
            )
            self.message_queue.put(("progress", 15))
            check_stop()
            
            # Step 4: Parallel transcription (15% → 70%)
            self.message_queue.put(("status", f"Step 4/5: Transcribing {len(chunk_files)} chunks in parallel..."))
            
            # Progress callback that updates based on chunks
            chunk_progress_base = 15
            chunk_progress_range = 55  # 15% to 70%
            
            def transcribe_progress(msg):
                # Extract chunk progress from message
                if "Transcribed" in msg and "/" in msg:
                    parts = msg.split()
                    for part in parts:
                        if "/" in part:
                            try:
                                current, total = part.split("/")
                                pct = int(current) / int(total)
                                progress_value = chunk_progress_base + (pct * chunk_progress_range)
                                self.message_queue.put(("progress", int(progress_value)))
                            except:
                                pass
                self.message_queue.put(("status", f"Step 4/5: {msg}"))
                check_stop()  # Check after each chunk
            
            result = transcriber.transcribe_parallel(
                chunk_files,
                progress_callback=transcribe_progress
            )
            
            transcript = result["text"]
            transcript_with_timestamps = transcriber.format_transcript_with_timestamps(result)
            
            self.message_queue.put(("progress", 70))
            check_stop()
            
            if not transcript.strip():
                self.message_queue.put(("status", "No speech detected in video."))
                self.message_queue.put(("done", None))
                return
            
            # Send transcript to UI
            self.message_queue.put(("transcript", transcript_with_timestamps))
            self.current_transcript = transcript_with_timestamps
            
            # Step 5: Summarize (70% → 100%)
            check_stop()
            self.message_queue.put(("status", "Step 5/5: Loading summarization model..."))
            self.message_queue.put(("progress", 75))
            
            summarizer = Summarizer()
            summarizer.load_model(
                progress_callback=lambda msg: self.message_queue.put(("status", f"Step 5/5: {msg}"))
            )
            
            self.message_queue.put(("status", "Step 5/5: Generating summary..."))
            self.message_queue.put(("progress", 85))
            
            summary = summarizer.summarize(
                transcript,
                word_limit=summary_words,
                progress_callback=lambda msg: self.message_queue.put(("status", f"Step 5/5: {msg}"))
            )
            
            self.message_queue.put(("progress", 100))
            
            # Send summary to UI
            self.message_queue.put(("summary", summary))
            self.current_summary = summary
            
            # Calculate elapsed time
            elapsed = time.time() - self.start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            
            self.message_queue.put(("status", f"✅ Complete in {mins}m {secs}s! Transcript and summary generated."))
            
            # Cleanup
            processor.cleanup_temp_files()
            processor.cleanup_chunks()
            
        except InterruptedError:
            self.message_queue.put(("status", "⏹️ Processing stopped by user"))
            self.message_queue.put(("stopped", None))
            # Cleanup on stop
            try:
                processor.cleanup_temp_files()
                processor.cleanup_chunks()
            except:
                pass
        
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n\nDetails:\n{traceback.format_exc()}"
            self.message_queue.put(("error", error_msg))
        
        finally:
            self.message_queue.put(("done", None))
    
    def _process_messages(self):
        """Process messages from background thread (runs on main thread)."""
        try:
            while True:
                msg_type, msg_data = self.message_queue.get_nowait()
                
                if msg_type == "status":
                    self.status_label.configure(text=msg_data)
                    
                elif msg_type == "progress":
                    self.progress["value"] = msg_data
                    
                elif msg_type == "transcript":
                    self.transcript_text.delete(1.0, tk.END)
                    self.transcript_text.insert(tk.END, msg_data)
                    self.save_transcript_btn.configure(state=tk.NORMAL)
                    
                elif msg_type == "summary":
                    self.summary_text.delete(1.0, tk.END)
                    self.summary_text.insert(tk.END, msg_data)
                    self.save_summary_btn.configure(state=tk.NORMAL)
                    
                elif msg_type == "error":
                    messagebox.showerror("Error", msg_data)
                    self.status_label.configure(text="❌ Error occurred", fg=self.highlight_color)
                    
                elif msg_type == "done":
                    self.select_btn.configure(state=tk.NORMAL)
                    self.process_btn.configure(state=tk.NORMAL)
                    self.stop_btn.configure(state=tk.DISABLED)
                    self.processing = False
                    self.stop_requested = False
                
                elif msg_type == "stopped":
                    self.select_btn.configure(state=tk.NORMAL)
                    self.process_btn.configure(state=tk.NORMAL)
                    self.stop_btn.configure(state=tk.DISABLED)
                    self.processing = False
                    self.stop_requested = False
                    self.status_label.configure(fg=self.warning_color)
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self._process_messages)
    
    def _save_transcript(self):
        """Save transcript to file."""
        if not self.current_transcript:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_name = Path(self.current_video).stem if self.current_video else "video"
        default_name = f"{video_name}_transcript_{timestamp}.txt"
        
        # Create outputs directory if needed
        outputs_dir = Path(__file__).parent / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name,
            initialdir=str(outputs_dir)
        )
        
        if filepath:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text(self.current_transcript, encoding="utf-8")
            messagebox.showinfo("Saved", f"Transcript saved to:\n{filepath}")
    
    def _save_summary(self):
        """Save summary to file."""
        if not self.current_summary:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_name = Path(self.current_video).stem if self.current_video else "video"
        default_name = f"{video_name}_summary_{timestamp}.md"
        
        # Create outputs directory if needed
        outputs_dir = Path(__file__).parent / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name,
            initialdir=str(outputs_dir)
        )
        
        if filepath:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text(self.current_summary, encoding="utf-8")
            messagebox.showinfo("Saved", f"Summary saved to:\n{filepath}")
    
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    app = FastVideoSummaryApp()
    app.run()


if __name__ == "__main__":
    main()
