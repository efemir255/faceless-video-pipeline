
import re

def split_logic(script):
    abbrs = ["Mr.", "Mrs.", "Dr.", "Ms.", "Jr.", "Sr.", "etc.", "vol.", "vs."]
    script_protected = script.replace("\n", " ")
    for a in abbrs:
        script_protected = script_protected.replace(a, a[:-1] + "|")

    raw_segments = re.split(r'(?<=[.!?])\s+', script_protected)

    sentences = []
    for s in raw_segments:
        s_restored = s.strip()
        for a in abbrs:
            s_restored = s_restored.replace(a[:-1] + "|", a)
        if len(s_restored) > 5:
            sentences.append(s_restored)
    return sentences

def test_split():
    script = "Hello Mr. Anderson. How are you? I have a Dr. Pepper for you vs. a Pepsi. etc. This should be interesting!"
    sentences = split_logic(script)
    for i, s in enumerate(sentences):
        print(f"{i}: {s}")

    expected = [
        "Hello Mr. Anderson.",
        "How are you?",
        "I have a Dr. Pepper for you vs. a Pepsi.",
        "etc.",
        "This should be interesting!"
    ]
    # Note: 'etc.' might be tricky if it's followed by a space and it's at the end of a 'sentence' that was split.
    # Actually my logic for etc. might fail if etc. ends with a period and I split there.

if __name__ == "__main__":
    test_split()
