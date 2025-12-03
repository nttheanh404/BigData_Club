#!/bin/bash
set -e

echo "[INFO] Starting OHLCV 1m Kafka Producer..."

BASE_DIR=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONPATH=$BASE_DIR

python3 "$BASE_DIR/services/producer/ohlcv_1m_producer.py"