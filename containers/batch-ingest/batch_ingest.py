import os
import requests
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, LongType, DoubleType, StringType, TimestampType
import pyspark.sql.functions as F

# CONFIG
def get_env(key, default=None):
    val = os.getenv(key, default)
    if val is None:
        print(f"[WARN] Env var {key} not found, using default: {default}")
    return val

HDFS_BASE_PATH = get_env("HDFS_BASE_PATH", "hdfs://hdfs-service:9000/data/crypto")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"] 

TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h"
}

LIMIT = 600  # ~10hours of history

def fetch_candles(symbol, api_interval, limit):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": api_interval, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        processed_data = []
        for row in data:
            # 0: Open Time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume
            processed_data.append((
                int(row[0]), float(row[1]), float(row[2]), float(row[3]), 
                float(row[4]), float(row[5]), symbol
            ))
        return processed_data
    except Exception as e:
        print(f"[ERROR] Fetching {symbol} {api_interval}: {e}")
        return []

def main():
    spark = SparkSession.builder \
        .appName("BatchLayerIngestion") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://hdfs-service:9000") \
        .getOrCreate()
    
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

    for folder_name, api_interval in TIMEFRAMES.items():
        print(f"\n>>> Processing Timeframe: {folder_name} (API: {api_interval})")
        all_tf_data = []
        
        for symbol in SYMBOLS:
            print(f"   Fetching {LIMIT} candles for {symbol}...")
            candles = fetch_candles(symbol, api_interval, LIMIT)
            if candles:
                all_tf_data.extend(candles)
        
        if not all_tf_data:
            print("   [WARN] No data fetched.")
            continue

        df = spark.createDataFrame(all_tf_data, schema)
        df = df.withColumn("timestamp", (F.col("timestamp_ms") / 1000).cast(TimestampType())).drop("timestamp_ms")
        
        output_path = f"{HDFS_BASE_PATH}/{folder_name}"
        
        # [CRITICAL FIX] PARTITION ALIGNMENT
        if folder_name == "1m":
            # Stream expects 1m to be partitioned by Symbol AND Date
            print(f"   [INFO] Partitioning {folder_name} by Symbol + Date...")
            df = df.withColumn("date", F.to_date("timestamp"))
            df.write.mode("overwrite").partitionBy("symbol", "date").parquet(output_path)
        else:
            # Others are partitioned by Symbol only
            print(f"   [INFO] Partitioning {folder_name} by Symbol...")
            df.write.mode("overwrite").partitionBy("symbol").parquet(output_path)
            
        print(f"   [SUCCESS] Wrote {df.count()} rows to {output_path}.")

    spark.stop()

if __name__ == "__main__":
    main()
