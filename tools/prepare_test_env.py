"""Prepare a persistent Python 3.12 environment using the hashed dependency export."""
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info[:2] != (3, 12):
        print("Install Python 3.12 with Tk support, then run this setup script with that interpreter.", file=sys.stderr)
        return 1
    import os
    interpreter = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    try:
        if not interpreter.is_file():
            print("Creating .venv with Python 3.12…", flush=True)
            venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
        # uv-created environments may not contain pip; ensurepip is local/offline.
        subprocess.run([str(interpreter), "-m", "ensurepip", "--upgrade"], check=True)
        subprocess.run([str(interpreter), "-m", "pip", "install", "--require-hashes", "-r", str(ROOT / "requirements.txt")], check=True)
        subprocess.run([str(interpreter), str(ROOT / "storm_tracker_gui.py"), "--check"], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Setup failed: {exc}\nOn Debian/Ubuntu, ensure python3.12-venv and python3-tk are installed.", file=sys.stderr)
        return 1
    print("Ready. Launch with start.bat on Windows or ./start.sh on Linux/macOS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
