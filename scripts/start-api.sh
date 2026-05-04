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
    raise SystemExit("本项目需要 Python 3.10+。建议使用 Docker 启动 API：docker compose up -d api")
PY

export PYTHONPATH="$(pwd)"
"$PYTHON_BIN" -m uvicorn app.api.server:app --host 0.0.0.0 --port "${API_HOST_PORT:-8000}"
