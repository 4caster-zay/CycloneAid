"""Check the release's single version source and tag consistency."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cycloneaid.metadata import __version__

root = Path(__file__).resolve().parents[1]
for filename in ("README.md", "CHANGELOG.md"):
    if __version__ not in (root/filename).read_text(encoding="utf-8"):
        raise SystemExit(f"{filename} does not identify {__version__}")
result = subprocess.run(["git", "describe", "--exact-match", "--tags", "HEAD"], cwd=root,
                        capture_output=True, text=True)
if result.returncode == 0 and result.stdout.strip() != f"v{__version__}":
    raise SystemExit("HEAD tag does not match the application version")
print(f"Release metadata consistent: {__version__}")
