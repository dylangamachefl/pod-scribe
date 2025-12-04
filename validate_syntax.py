"""
Syntax validation script for refactored modules.
Tests that all modules can be parsed without runtime dependencies.
"""
import py_compile
import sys
from pathlib import Path

# Base paths
project_root = Path(__file__).parent
transcription_src = project_root / "transcription-service" / "src"

# Modules to test
modules_to_test = [
    transcription_src / "config.py",
    transcription_src / "cli.py",
    transcription_src / "main.py",
    transcription_src / "core" / "audio.py",
    transcription_src / "core" / "diarization.py",
    transcription_src / "core" / "formatting.py",
    transcription_src / "core" / "processor.py",
]

print("🔍 Validating Python syntax for refactored modules...\n")

all_valid = True
for module_path in modules_to_test:
    try:
        py_compile.compile(str(module_path), doraise=True)
        print(f"✅ {module_path.relative_to(project_root)}")
    except py_compile.PyCompileError as e:
        print(f"❌ {module_path.relative_to(project_root)}: {e}")
        all_valid = False

print()
if all_valid:
    print("✅ All modules have valid Python syntax!")
    sys.exit(0)
else:
    print("❌ Some modules have syntax errors")
    sys.exit(1)
