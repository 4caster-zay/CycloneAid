"""Bounded local diagnostics for render failures and Tk callback exceptions."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import traceback

LOGGER = logging.getLogger('cycloneaid')
LOGGER.addHandler(logging.NullHandler())


def configure_logging(directory=None):
    if directory is None:
        root = Path(__file__).resolve().parents[1]
        if (root/'pyproject.toml').is_file():
            directory = root/'.cache'/'logs'
        else:
            state = os.environ.get('LOCALAPPDATA') if os.name == 'nt' else os.environ.get('XDG_STATE_HOME')
            directory = Path(state or Path.home()/'.local'/'state')/'cycloneaid'/'logs'
    path = Path(directory)/'cycloneaid.log'
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not any(getattr(handler, 'baseFilename', None) == str(path.resolve()) for handler in LOGGER.handlers):
            handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=2, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            LOGGER.addHandler(handler)
        LOGGER.setLevel(logging.INFO)
        LOGGER.propagate = False
        return path
    except OSError:
        return None  # Diagnostics must not prevent the application from starting.


def error_message(context, error, detail=None):
    detail = detail or traceback.format_exc()
    if detail.strip() == 'NoneType: None':
        detail = str(error)
    LOGGER.error('%s: %s\n%s', context, error, detail)
    print(f'{context}: {error}\n{detail}', file=sys.stderr)
    paths = [handler.baseFilename for handler in LOGGER.handlers if isinstance(handler, logging.FileHandler)]
    return str(error) + (f'\n\nDiagnostic log: {paths[-1]}' if paths else '\n\nDetails were written to the terminal.')
