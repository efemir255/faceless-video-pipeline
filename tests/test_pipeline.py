import unittest
import re

def split_script(script: str):
    """Internal helper logic copied from video_fetcher.py for testing."""
    raw_segments = re.split(r'(?<=[.!?])\s+', script.replace("\n", " "))
    sentences = [s.strip() for s in raw_segments if len(s.strip()) > 5]
    if not sentences:
        sentences = [script.strip()]
    return sentences

class TestPipelineLogic(unittest.TestCase):
    def test_script_splitting(self):
        script = "This is sentence one. This is sentence two! And three?"
        segments = split_script(script)
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0], "This is sentence one.")
        self.assertEqual(segments[1], "This is sentence two!")
        self.assertEqual(segments[2], "And three?")

    def test_script_splitting_with_newlines(self):
        script = "Line one.\nLine two."
        segments = split_script(script)
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

if __name__ == "__main__":
    unittest.main()
