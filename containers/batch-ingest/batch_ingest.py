import os
import requests
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, LongType, DoubleType, StringType, TimestampType
import pyspark.sql.functions as F

# =========================================================
# 1. CONFIGURATION
# =========================================================
def get_env(key, default=None):
    val = os.getenv(key, default)
    if val is None:
        print(f"[WARN] Env var {key} not found, using default: {default}")
    return val

# HDFS Configs (Must match Stream Layer)
# If your stream reads from /data/crypto, this must write to /data/crypto
HDFS_BASE_PATH = get_env("HDFS_BASE_PATH", "hdfs://hdfs-service:9000/data/crypto")

# Symbols to track
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"] 

# Timeframes to fetch
# Map: "Folder Name" -> "Binance API Interval"
TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h"
}

LIMIT = 300 # How many past candles to fetch

# =========================================================
# 2. SPARK SESSION
# =========================================================
def get_spark_session():
    return SparkSession.builder \
        .appName("BatchLayerIngestion") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://hdfs-service:9000") \
        .getOrCreate()

# =========================================================
# 3. HELPER FUNCTIONS
# =========================================================
def fetch_candles(symbol, api_interval, limit):
    """
    Fetches K-lines from Binance API.
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": api_interval,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # Binance returns: [Open Time, Open, High, Low, Close, Volume, Close Time, ...]
        processed_data = []
        for row in data:
            processed_data.append((
                int(row[0]),      # timestamp_ms
                float(row[1]),    # open
                float(row[2]),    # high
                float(row[3]),    # low
                float(row[4]),    # close
                float(row[5]),    # volume
                symbol
            ))
        return processed_data
    except Exception as e:
        print(f"[ERROR] Fetching {symbol} {api_interval}: {e}")
        return []

def main():
    spark = get_spark_session()
    
    # Schema must match what the Stream Layer expects
    schema = StructType([
        StructField("timestamp_ms", LongType(), True),
        StructField("open", DoubleType(), True),
        StructField("high", DoubleType(), True),
        StructField("low", DoubleType(), True),
        StructField("close", DoubleType(), True),
        StructField("volume", DoubleType(), True),
        StructField("symbol", StringType(), True)
    ])

    print(f"--- Starting Batch Ingestion ---")
    print(f"Target HDFS Base: {HDFS_BASE_PATH}")

    # Loop through each timeframe folder (1m, 5m, 1h...)
    for folder_name, api_interval in TIMEFRAMES.items():
        print(f"\n>>> Processing Timeframe: {folder_name} (API: {api_interval})")
        
        all_tf_data = []
        
        # Fetch data for all symbols for THIS timeframe
        for symbol in SYMBOLS:
            print(f"   Fetching {LIMIT} candles for {symbol}...")
            candles = fetch_candles(symbol, api_interval, LIMIT)
            if candles:
                all_tf_data.extend(candles)
        
        if not all_tf_data:
            print(f"   [WARN] No data found for {folder_name}. Skipping.")
            continue

        # Create DataFrame
        df = spark.createDataFrame(all_tf_data, schema)

        # Convert timestamp_ms to Timestamp Type (Stream layer needs this)
        df = df.withColumn("timestamp", (F.col("timestamp_ms") / 1000).cast(TimestampType())) \
               .drop("timestamp_ms")

        # Define Output Path (e.g., /data/crypto/1m)
        output_path = f"{HDFS_BASE_PATH}/{folder_name}"
        
        print(f"   Writing {df.count()} rows to {output_path}...")
        
        # Write to HDFS
        # mode("overwrite") ensures we reset the batch layer state freshly every time it runs
        # partitionBy("symbol") makes it easy for Hive/Spark to query later
        try:
            df.write \
                .mode("overwrite") \
                .partitionBy("symbol") \
                .parquet(output_path)
            print(f"   [SUCCESS] Wrote {folder_name} to HDFS.")
        except Exception as e:
            print(f"   [ERROR] Failed writing to HDFS: {e}")

    print("\n--- Batch Ingestion Complete ---")
    spark.stop()

if __name__ == "__main__":
    main()