"""Dependency-light desktop bootstrap for source checkouts and installed apps."""
import argparse
import importlib
import os
from pathlib import Path
import sys

from cycloneaid.metadata import __version__

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = ("tkinter", "numpy", "pandas", "matplotlib", "cartopy", "shapely", "pyproj", "rtree", "PIL")


def project_python(root=ROOT):
    """Prefer the checkout's persistent environment without resolving its symlink."""
    if not (root / "pyproject.toml").is_file():
        return None  # Installed wheel: use the interpreter which owns the entry point.
    candidate = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if candidate.is_file() and Path(sys.prefix).resolve() != (root / ".venv").resolve():
        return candidate
    return None


def configure_runtime(root=ROOT):
    if (root / "pyproject.toml").is_file():
        if "MPLCONFIGDIR" not in os.environ:
            cache = root / ".cache" / "matplotlib"
            cache.mkdir(parents=True, exist_ok=True)
            os.environ["MPLCONFIGDIR"] = str(cache)
        geography = root / ".cache" / "cartopy"
        if geography.is_dir():
            os.environ.setdefault("CARTOPY_DATA_DIR", str(geography))


def check_environment():
    problems = []
    if sys.version_info[:2] != (3, 12):
        problems.append(f"Python 3.12 is required; this interpreter is {sys.version_info.major}.{sys.version_info.minor}")
    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
        except (ImportError, OSError) as exc:
            problems.append(f"{name}: {exc}")
    return problems


def _setup_hint():
    if (ROOT / "pyproject.toml").is_file():
        command = "setup.bat" if os.name == "nt" else "./setup.sh"
        return f"From {ROOT}, run {command}, then launch again."
    return "Reinstall CycloneAid with its desktop dependencies using Python 3.12."


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    interpreter = project_python()
    if interpreter is not None:
        os.execv(str(interpreter), [str(interpreter), str(ROOT / "storm_tracker_gui.py"), *argv])
    parser = argparse.ArgumentParser(description="Launch CycloneAid using the project's Python environment")
    parser.add_argument("--check", action="store_true", help="Check Python and dependencies without opening a window")
    args = parser.parse_args(argv)
    configure_runtime()
    problems = check_environment()
    if problems:
        print("CycloneAid cannot start:\n" + "\n".join(f"  - {problem}" for problem in problems), file=sys.stderr)
        print(_setup_hint(), file=sys.stderr)
        return 1
    if args.check:
        print(f"CycloneAid {__version__}")
        print(f"Python: {sys.version.split()[0]}")
        print(f"Interpreter: {sys.executable}")
        print("Required dependencies and Tk: OK")
        try:
            importlib.import_module("tkintermapview")
            print("Interactive map: available")
        except ImportError:
            print("Interactive map: optional package absent; table/chart testing is available")
        from cycloneaid.geography import geography_readiness
        missing = geography_readiness()
        print("Full-geography assets: " + ("ready" if not missing else
              "not cached; use Prepare map assets or degraded geography"))
        print("Display connection is checked when opening the GUI.")
        return 0
    import tkinter as tk
    try:
        from storm_tracker_gui import StormTrackerApp
        StormTrackerApp().mainloop()
    except tk.TclError as exc:
        print(f"CycloneAid could not open its desktop window: {exc}", file=sys.stderr)
        print("Run the launcher from a terminal in your graphical desktop session. "
              "A display server is required; --check can run without one.", file=sys.stderr)
        return 1
    return 0
