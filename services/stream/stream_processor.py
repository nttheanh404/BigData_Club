"""
Service: stream_processor.py
--------------------------
Kafka → Spark Structured Streaming → Model Predict → Elasticsearch

Reads JSON OHLCV messages from Kafka, applies trained XGBoost model
to predict price direction ("UP"/"DOWN"), then writes to Elasticsearch.

Author: Mysorf
"""

import os
import pandas as pd
import numpy as np

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, udf
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType

# Kafka
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_OHLCV_1M_TOPIC", "crypto_ohlcv_1m")

# Elasticsearch
ES_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
ES_PORT = os.getenv("ELASTICSEARCH_PORT", "9200")

ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "crypto_ohlcv_1m_pred")

# Streaming
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "/tmp/stream-checkpoint-es")

WRITE_TO_CONSOLE = (
    os.getenv("WRITE_TO_CONSOLE", "false").lower() == "true"
    or not (ES_HOST and ES_PORT)
)

# Model paths
MODEL_PATH = os.getenv("MODEL_PATH", "../models/xgb_model.pkl")
SCALER_PATH = os.getenv("SCALER_PATH", "../models/scaler.pkl")

# Schema Kafka message
schema = StructType([
  StructField("symbol", StringType()),
  StructField("exchange", StringType()),
  StructField("@timestamp", StringType()),
  StructField("timestamp_ms", LongType()),
  StructField("open", DoubleType()),
  StructField("high", DoubleType()),
  StructField("low", DoubleType()),
  StructField("close", DoubleType()),
  StructField("volume", DoubleType()),
])


# Load model & scaler
def load_model():
  print(f"[INFO] Loading model: {MODEL_PATH} and scaler: {SCALER_PATH} ...")
  import pickle
  with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)
  with open(SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)
  return model, scaler


MODEL, SCALER = load_model()
TRAIN_FEATURES = ["open", "high", "low", "close"]


# Predict udf
def predict_direction(open_, high_, low_, close_, volume_):
  """
  Get 5 fields from the stream but only use the 4 trained fields (open, high, low, close).
  Use NumPy instead of DataFrame to avoid 'feature names' warning.
  """
  if None in (open_, high_, low_, close_):
    return "UNKNOWN"
  try:
    # Important: keep the same order of features as when training
    X = np.array([[open_, high_, low_, close_]], dtype=float)
    X_scaled = SCALER.transform(X)
    pred = MODEL.predict(X_scaled)
    return "UP" if int(pred[0]) == 1 else "DOWN"
  except Exception as e:
    print("[WARN] Prediction error:", e)
    return "ERROR"


predict_udf = udf(predict_direction, StringType())


# Elasticsearch client & writer
def make_es_client():
  from elasticsearch import Elasticsearch
  es = Elasticsearch(f"http://{ES_HOST}:{ES_PORT}")
  es_admin = es.options(ignore_status=[400])

  if not es.ping():
    raise ConnectionError(f"Cannot connect to Elasticsearch at {ES_HOST}:{ES_PORT}")

  if not es.indices.exists(index=ES_INDEX):
    es_admin.indices.create(index=ES_INDEX)

  return es


def write_batch_to_es(batch_df, batch_id: int):
  """
  Used in foreachBatch: receive DataFrame (1 micro-batch) and bulk index to ES.
  """
  count = batch_df.count()
  if count == 0:
    return

  es = make_es_client()

  # Get only fields that need + prediction
  cols = [
    "symbol", "exchange", "ts_iso", "timestamp_ms",
    "open", "high", "low", "close", "volume", "prediction"
  ]
  df_pd = batch_df.select(*cols).toPandas()

  from elasticsearch import helpers
  actions = (
    {
      "_index": ES_INDEX,
      "_source": {
        "@timestamp": row["ts_iso"] or None,
        "timestamp_ms": int(row["timestamp_ms"]) if pd.notna(row["timestamp_ms"]) else None,
        "symbol": row["symbol"],
        "exchange": row["exchange"],
        "open": float(row["open"]) if pd.notna(row["open"]) else None,
        "high": float(row["high"]) if pd.notna(row["high"]) else None,
        "low": float(row["low"]) if pd.notna(row["low"]) else None,
        "close": float(row["close"]) if pd.notna(row["close"]) else None,
        "volume": float(row["volume"]) if pd.notna(row["volume"]) else None,
        "prediction": row["prediction"],
      },
    }
    for _, row in df_pd.iterrows()
  )

  helpers.bulk(es, actions)
  print(f"[ES] Indexed batch_id={batch_id} docs={len(df_pd)} into index={ES_INDEX}")


# Main
def main():
  spark = (
    SparkSession.builder
    .appName("stream-ohlcv-predict")
    # AQE does not support streaming → disable to remove warning
    .config("spark.sql.adaptive.enabled", "false")
    # Soft shutdown
    .config("spark.streaming.stopGracefullyOnShutdown", "true")
    # Fix Hadoop UGI getSubject bug on macOS + Java >= 17
    .config("spark.hadoop.fs.file.impl.disable.cache", "true")
    .config("spark.hadoop.fs.AbstractFileSystem.file.impl", "org.apache.hadoop.fs.local.LocalFs")
    .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_DIR)
    .getOrCreate()
  )
  spark.sparkContext.setLogLevel("WARN")

  # Read from Kafka stream
  raw = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BROKER)
    .option("subscribe", KAFKA_TOPIC)
    .option("startingOffsets", "latest")
    # Limit time
    .option("maxOffsetsPerTrigger", "2000")
    .load()
  )

  # Parse JSON
  parsed = (
    raw.selectExpr("CAST(value AS STRING) AS json")
    .select(from_json(col("json"), schema).alias("data"))
    .select("data.*")
    .withColumnRenamed("@timestamp", "ts_iso")
  )

  # Apply Prediction
  predicted = parsed.withColumn(
    "prediction",
    predict_udf(col("open"), col("high"), col("low"), col("close"), col("volume"))
  )

  # Checkpoint args
  checkpoint_args = {"checkpointLocation": CHECKPOINT_DIR}

  if WRITE_TO_CONSOLE:
    query = (
      predicted.writeStream
      .outputMode("append")
      .format("console")
      .option("truncate", "false")
      .option("numRows", 20)
      .options(**checkpoint_args)
      .start()
    )
    print("[INFO] Writing PREDICTIONS to CONSOLE sink…")
  else:
    query = (
      predicted.writeStream
      .outputMode("append")
      .foreachBatch(lambda df, bid: write_batch_to_es(df, bid))
      .options(**checkpoint_args)
      .start()
    )
    print(f"[INFO] Writing PREDICTIONS to Elasticsearch http://{ES_HOST}:{ES_PORT} index={ES_INDEX} via foreachBatch")

  query.awaitTermination()


if __name__ == "__main__":
  main()