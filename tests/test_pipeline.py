import unittest
import re
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_fetcher import split_script_into_sentences

class TestPipelineLogic(unittest.TestCase):
    def test_script_splitting(self):
        script = "This is sentence one. This is sentence two! And three?"
        segments = split_script_into_sentences(script)
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0], "This is sentence one.")
        self.assertEqual(segments[1], "This is sentence two!")
        self.assertEqual(segments[2], "And three?")

    def test_script_splitting_with_newlines(self):
        script = "Line one.\nLine two."
        segments = split_script_into_sentences(script)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], "Line one.")
        self.assertEqual(segments[1], "Line two.")

    def test_duration_calculation(self):
        """Test the logic for proportional duration calculation."""
        sentences = ["One", "Two", "Three"]
        total_duration = 30.0

        all_sentence_words = [len(s.split()) for s in sentences]
        total_sentence_words = sum(all_sentence_words)

        durations = [(w / total_sentence_words) * total_duration for w in all_sentence_words]
        self.assertEqual(sum(durations), 30.0)
        for d in durations:
            self.assertEqual(d, 10.0)

    def test_keyword_extraction(self):
        """Test the logic for refining keywords."""
        stop_words = {"the", "and", "a", "an", "is", "are", "of", "to", "in", "it", "that", "this", "for", "with", "as", "at"}
        sentence = "This is a test of the emergency broadcast system!"

        # Logic from video_fetcher.py
        clean_words = [w.lower() for w in re.findall(r'\b\w+\b', sentence) if w.lower() not in stop_words]
        snippet = " ".join(clean_words[:3])

        self.assertEqual(snippet, "test emergency broadcast")

if __name__ == "__main__":
    unittest.main()
