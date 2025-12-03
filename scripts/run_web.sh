#!/bin/bash
set -e

echo "[INFO] Starting Web Dashboard..."

cd "$(dirname "$0")/.."

# Env
export ES_URL=http://localhost:9200
export ES_INDEX=crypto_ohlcv_1m_pred
export PORT=8000

# Run web app
python3 -m uvicorn services.web.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload