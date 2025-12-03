#!/bin/bash
set -e

export JAVA_HOME=$(/usr/libexec/java_home -v 17)
echo "[INFO] Using JAVA_HOME=$JAVA_HOME"
java -version

export KAFKA_BROKER=localhost:9092
export KAFKA_OHLCV_1M_TOPIC=crypto_ohlcv_1m
export CHECKPOINT_DIR=/tmp/stream-checkpoint-es
export WRITE_TO_CONSOLE=false

export ELASTICSEARCH_HOST=localhost
export ELASTICSEARCH_PORT=9200
export ELASTICSEARCH_INDEX=crypto_ohlcv_1m_pred

export MODEL_PATH=../models/xgb_model.pkl
export SCALER_PATH=../models/scaler.pkl

spark-submit \
  --master local[2] \
  --conf spark.hadoop.fs.file.impl.disable.cache=true \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  ../services/stream/stream_processor.py