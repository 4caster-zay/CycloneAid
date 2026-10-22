"""Single source for application and distribution metadata."""
__version__ = "0.11.0a1"
APP_NAME = "CycloneAid"
CREATOR = "Forecaster Zayed"
DISPLAY_VERSION = f"{__version__} (Alpha 1)"
CONE_METHOD = "legacy-heuristic-v1"


def display_storm_name(name):
    """Return a readable title without modifying the saved operator input."""
    return str(name or "").strip() or "Untitled storm"
