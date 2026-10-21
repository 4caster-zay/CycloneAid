#!/usr/bin/env bash
set -euo pipefail
cycloneaid_project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$cycloneaid_project_dir/.venv/bin/python" ]]; then
    exec "$cycloneaid_project_dir/.venv/bin/python" "$cycloneaid_project_dir/storm_tracker_gui.py" "$@"
fi
exec python3 "$cycloneaid_project_dir/storm_tracker_gui.py" "$@"
