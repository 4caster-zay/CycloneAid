#!/usr/bin/env bash
set -euo pipefail
cycloneaid_project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3.12 >/dev/null 2>&1; then
    cycloneaid_python=python3.12
else
    cycloneaid_python=python3
fi
exec "$cycloneaid_python" "$cycloneaid_project_dir/tools/prepare_test_env.py"
