#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("本项目需要 Python 3.10+。当前解释器过低，建议使用 Docker 启动：bash scripts/start-docker.sh")
PY

export PYTHONPATH="$(pwd)"
"$PYTHON_BIN" -m streamlit run app/ui/streamlit_app.py --server.address=0.0.0.0 --server.port=8501
