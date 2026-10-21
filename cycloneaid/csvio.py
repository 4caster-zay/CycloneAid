"""Atomic forecast interchange export (project settings belong in project files)."""
from dataclasses import asdict
import os
from pathlib import Path
import tempfile
import pandas as pd


def export_csv(points, path):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=path.parent,
                                         suffix='.csv', delete=False) as handle:
            temporary = Path(handle.name)
            rows = []
            for point in points:
                row = asdict(point)
                row['time'] = point.time.isoformat()
                rows.append(row)
            pd.DataFrame(rows).to_csv(handle, index=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
