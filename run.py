"""Use the project's own Python environment without requiring shell activation."""

import os
from pathlib import Path

root = Path(__file__).resolve().parent
python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.is_file():
    raise SystemExit("Create .venv and install this project's dependencies first. See README.md.")
os.chdir(root)
os.execv(str(python), [str(python), "-m", "voice_debugger.launcher"])
