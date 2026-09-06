from __future__ import annotations

from pathlib import Path


ROOT = Path('C:\\Jarvis')

# The voice compile test should pass the native Windows path directly to csc.
# Python runtime interpolation already produces the correct path string; no
# doubled backslash transformation is needed.
voice_path = ROOT / "tests" / "test_jarvis_v32_hybrid_voice.py"
source = voice_path.read_text(encoding="utf-8")
old = '            f"\'/out:{str(output).replace(chr(92), chr(92)+chr(92))}\' "\n'
new = '            f"\'/out:{output}\' "\n'
if old in source:
    source = source.replace(old, new, 1)
elif new not in source:
    raise RuntimeError("V6 voice compile post-fix anchor not found")
voice_path.write_text(source, encoding="utf-8", newline="\n")

print("Voice unique compile path normalization: PASS")
