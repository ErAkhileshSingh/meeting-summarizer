"""
Summarizer Module
Uses sshleifer/distilbart-cnn-12-6 for fast, high-quality summarization.
"""

import os
from pathlib import Path
from transformers import BartForConditionalGeneration, BartTokenizer
from datetime import datetime


# Set cache directory to project folder
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "distilbart"
os.environ["HF_HOME"] = str(MODELS_DIR)
os.environ["TRANSFORMERS_CACHE"] = str(MODELS_DIR)


class Summarizer:
    """Summarizes meeting transcripts using DistilBART (2x faster than BART-large)."""
    
    MODEL_NAME = "sshleifer/distilbart-cnn-12-6"  # 2x faster than bart-large-cnn
    
    def __init__(self, model_dir: str = None):
        """
        Initialize the summarizer.
        
        Args:
            model_dir: Directory to store/load models
        """
        self.model_dir = model_dir or str(MODELS_DIR)
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        
        # Ensure model directory exists
        Path(self.model_dir).mkdir(parents=True, exist_ok=True)
    
    def load_model(self, progress_callback=None):
        """
        Load the DistilBART model.
        
        Args:
            progress_callback: Optional callback for progress updates
        """
        if self.model is not None:
            return
        
        if progress_callback:
            progress_callback("Loading DistilBART model (~1GB, 2x faster)...")
        
        # Load tokenizer and model
        self.tokenizer = BartTokenizer.from_pretrained(
            self.MODEL_NAME,
            cache_dir=self.model_dir
        )
        
        self.model = BartForConditionalGeneration.from_pretrained(
            self.MODEL_NAME,
            cache_dir=self.model_dir
        )
        
        self.model.to(self.device)
        
        if progress_callback:
            progress_callback("DistilBART model loaded!")
    
    def summarize(self, transcript: str, word_limit: int = 800, progress_callback=None) -> str:
        """
        Summarize a meeting transcript with detailed, structured output.
        
        Args:
            transcript: The meeting transcript text
            word_limit: Target word count for the summary (default: 800)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Formatted summary string
        """
        if self.model is None:
            self.load_model(progress_callback)
        
        if progress_callback:
            progress_callback(f"Generating ~{word_limit} word summary...")
        
        # Clean transcript
        transcript = transcript.strip()
        
        if not transcript:
            return "No content to summarize."
        
        # Calculate chunk size based on word limit
        # More words needed = more chunks = smaller chunk size
        transcript_words = len(transcript.split())
        target_chunks = max(3, word_limit // 100)  # ~100 words per chunk summary
        max_chunk_length = max(400, transcript_words // target_chunks * 5)  # chars per chunk
        
        chunks = self._chunk_text(transcript, max_chunk_length)
        
        summaries = []
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(f"Summarizing chunk {i+1}/{len(chunks)}...")
            
            chunk_summary = self._summarize_chunk_detailed(chunk)
            if chunk_summary:
                summaries.append(chunk_summary)
        
        # Combine all chunk summaries
        detailed_summary = "\n\n".join(summaries)
        
        # Trim to approximate word limit if too long
        summary_words = detailed_summary.split()
        if len(summary_words) > word_limit * 1.2:
            detailed_summary = " ".join(summary_words[:word_limit])
            detailed_summary += "..."
        
        # Generate a brief executive summary from the detailed one
        if progress_callback:
            progress_callback("Generating executive summary...")
        
        exec_summary = self._summarize_chunk(detailed_summary[:2000]) if len(detailed_summary) > 500 else detailed_summary
        
        # Extract key points (simple extraction from chunks)
        key_points = self._extract_key_points(summaries)
        
        # Format final output with structured sections
        output = f"""# Meeting Summary
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Transcript Length:** {len(transcript):,} characters | {len(transcript.split()):,} words

---

## Executive Summary
{exec_summary}

---

## Detailed Summary

{detailed_summary}

---

## Key Points
{key_points}

---

## Action Items & Takeaways
Based on the meeting content, the following items require attention:

{self._generate_action_items(summaries)}

---

## Full Transcript
<details>
<summary>📜 Click to expand full transcript ({len(transcript):,} characters)</summary>

{transcript}

</details>

---
*Generated by Meeting Summary App using BART-large-CNN*
*Processing completed at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
        return output
    
    def _summarize_chunk_detailed(self, text: str) -> str:
        """Summarize a single chunk with more detail."""
        if not text.strip():
            return ""
        
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            max_length=1024,
            truncation=True
        ).to(self.device)
        
        # Generate longer summaries (fast with distilbart)
        summary_ids = self.model.generate(
            inputs["input_ids"],
            max_length=300,      # Keep long output
            min_length=80,       # Keep detailed
            length_penalty=1.5,
            num_beams=2,         # Reduced from 4 for 2x speed
            early_stopping=True,
            no_repeat_ngram_size=3
        )
        
        summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return summary
    
    def _extract_key_points(self, summaries: list) -> str:
        """Extract key points from summaries as bullet points."""
        points = []
        for i, summary in enumerate(summaries, 1):
            # Take first sentence or first 150 chars
            sentences = summary.split('.')
            if sentences:
                point = sentences[0].strip()
                if len(point) > 20:  # Only include substantial points
                    points.append(f"• {point}.")
        
        if not points:
            return "• Key points extracted from the meeting content above."
        
        return "\n".join(points[:10])  # Limit to 10 key points
    
    def _generate_action_items(self, summaries: list) -> str:
        """Generate action items from the content."""
        items = []
        action_keywords = ['should', 'need to', 'must', 'will', 'going to', 'plan to', 'want to', 'have to']
        
        combined = " ".join(summaries).lower()
        sentences = combined.replace('.', '.|').replace('!', '!|').replace('?', '?|').split('|')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword in sentence for keyword in action_keywords):
                if len(sentence) > 30 and len(sentence) < 200:
                    # Capitalize first letter
                    formatted = sentence[0].upper() + sentence[1:] if sentence else sentence
                    items.append(f"- [ ] {formatted}")
        
        if not items:
            items = [
                "- [ ] Review the key points from this meeting",
                "- [ ] Follow up on discussed topics",
                "- [ ] Share summary with relevant stakeholders"
            ]
        
        return "\n".join(items[:8])  # Limit to 8 action items
    
    def _chunk_text(self, text: str, max_length: int) -> list:
        """Split text into chunks for processing."""
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) > max_length and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks if chunks else [text]
    
    def _summarize_chunk(self, text: str) -> str:
        """Summarize a single chunk of text."""
        if not text.strip():
            return ""
        
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            max_length=1024,
            truncation=True
        ).to(self.device)
        
        summary_ids = self.model.generate(
            inputs["input_ids"],
            max_length=150,
            min_length=30,
            length_penalty=2.0,
            num_beams=4,
            early_stopping=True
        )
        
        summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return summary
    
    def get_model_size_mb(self) -> int:
        """Get approximate model size in MB."""
        return 1600  # BART-large-CNN is ~1.6GB


def test_summarizer():
    """Test the summarizer module."""
    print("Summarizer module loaded successfully!")
    print(f"Model: {Summarizer.MODEL_NAME}")
    print(f"Model directory: {MODELS_DIR}")


if __name__ == "__main__":
    test_summarizer()
