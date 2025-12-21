import os
import time
import traceback
import pandas as pd
import numpy as np
from functools import reduce
from pyspark.sql import SparkSession, DataFrame
import pyspark.sql.functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType, LongType

# =========================================================
# 1. CONFIGURATION
# =========================================================
def get_env(key, default=None):
    val = os.getenv(key, default)
    if val is None:
        print(f"[WARN] Env var {key} not found, using default: {default}")
    return val

KAFKA_BOOTSTRAP = get_env("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_TOPIC = get_env("KAFKA_TOPIC", "crypto_ohlcv_1m")

HDFS_BASE_PATH = get_env("HDFS_BASE_PATH", "hdfs://hdfs-service:9000/data/crypto")
CHECKPOINT_DIR = get_env("CHECKPOINT_DIR", "hdfs://hdfs-service:9000/data/checkpoints/crypto_stream")
LOOKBACK_DAYS = int(get_env("LOOKBACK_DAYS", "5")) 

ES_HOST = get_env("ES_HOST", "elasticsearch")
ES_PORT = get_env("ES_PORT", "9200")
ES_USER = get_env("ES_USER", "elastic")
ES_PASS = get_env("ES_PASS", "changeme")
ES_INDEX = get_env("ES_INDEX", "crypto_technical_analysis").split("/")[0]

ES_TRUSTSTORE_URI = get_env("ES_SSL_TRUSTSTORE_PATH", "") 
ES_TRUSTSTORE_FILE = ES_TRUSTSTORE_URI.replace("file://", "") if ES_TRUSTSTORE_URI else None
ES_TRUSTSTORE_PASS = get_env("ES_SSL_TRUSTSTORE_PASS", "changeit")

TIMEFRAMES = {
    "1m":  {"duration": "1 minute",   "minutes": 1},
    "5m":  {"duration": "5 minutes",  "minutes": 5},
    "15m": {"duration": "15 minutes", "minutes": 15},
    "1h":  {"duration": "1 hour",     "minutes": 60},
    "4h":  {"duration": "4 hours",    "minutes": 240}
}

# =========================================================
# 2. SCHEMAS
# =========================================================
input_schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("exchange", StringType(), True),
    StructField("timestamp_ms", LongType(), True),
    StructField("@timestamp", StringType(), True),
    StructField("open", DoubleType(), True),
    StructField("high", DoubleType(), True),
    StructField("low", DoubleType(), True),
    StructField("close", DoubleType(), True),
    StructField("volume", DoubleType(), True),
])

output_schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("open", DoubleType(), True),
    StructField("high", DoubleType(), True),
    StructField("low", DoubleType(), True),
    StructField("close", DoubleType(), True),
    StructField("volume", DoubleType(), True),
    StructField("ema_9", DoubleType(), True),
    StructField("ema_20", DoubleType(), True),
    StructField("ema_50", DoubleType(), True),
    StructField("ema_200", DoubleType(), True),
    StructField("macd_line", DoubleType(), True),
    StructField("macd_signal", DoubleType(), True),
    StructField("macd_hist", DoubleType(), True),
    StructField("rsi_14", DoubleType(), True),
    StructField("stoch_k", DoubleType(), True),
    StructField("stoch_d", DoubleType(), True),
    StructField("bb_upper", DoubleType(), True),
    StructField("bb_middle", DoubleType(), True),
    StructField("bb_lower", DoubleType(), True),
    StructField("atr_14", DoubleType(), True),
    StructField("obv", DoubleType(), True),
    StructField("timeframe", StringType(), True)
])

# =========================================================
# 3. SPARK INIT
# =========================================================
print(f"[INIT] Starting Processor...", flush=True)
print(f"[INIT] HDFS Base: {HDFS_BASE_PATH}", flush=True)

spark = (
    SparkSession.builder
    .appName("CryptoMultiFrameProcessor")
    .config("spark.hadoop.fs.defaultFS", "hdfs://hdfs-service:9000")
    .config("spark.sql.execution.arrow.pyspark.enabled", "false")
    .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
    .config("spark.network.timeout", "120s")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

# =========================================================
# 4. MATH LOGIC (UDF)
# =========================================================
def calculate_all_indicators_udf(pdf):
    if pdf.empty: return pd.DataFrame(columns=[f.name for f in output_schema.fields])
    pdf = pdf.sort_values("timestamp")
    close, high, low, volume = pdf['close'], pdf['high'], pdf['low'], pdf['volume']

    # Indicators
    pdf['ema_9'] = close.ewm(span=9, adjust=False).mean()
    pdf['ema_20'] = close.ewm(span=20, adjust=False).mean()
    pdf['ema_50'] = close.ewm(span=50, adjust=False).mean()
    pdf['ema_200'] = close.ewm(span=200, adjust=False).mean()

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    pdf['macd_line'] = ema_12 - ema_26
    pdf['macd_signal'] = pdf['macd_line'].ewm(span=9, adjust=False).mean()
    pdf['macd_hist'] = pdf['macd_line'] - pdf['macd_signal']

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    pdf['rsi_14'] = 100 - (100 / (1 + rs))

    low_14 = low.rolling(window=14).min()
    high_14 = high.rolling(window=14).max()
    pdf['stoch_k'] = 100 * ((close - low_14) / (high_14 - low_14 + 1e-9))
    pdf['stoch_d'] = pdf['stoch_k'].rolling(window=3).mean()

    pdf['bb_middle'] = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    pdf['bb_upper'] = pdf['bb_middle'] + (2 * bb_std)
    pdf['bb_lower'] = pdf['bb_middle'] - (2 * bb_std)

    prev_close = close.shift(1)
    tr = pd.concat([high-low, (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    pdf['atr_14'] = tr.rolling(window=14).mean()
    pdf['obv'] = (volume * np.sign(close.diff()).fillna(0)).cumsum()

    return pdf.fillna(0.0)

# =========================================================
# 5. BATCH PROCESSOR
# =========================================================
def process_batch(df_batch, batch_id):
    if df_batch.isEmpty(): return

    print(f"\n>>> [BATCH {batch_id}] Processing...", flush=True)
    df_batch.cache()

    # Get Metadata
    try:
        row_metadata = df_batch.agg(
            F.min("timestamp").alias("min_ts"), 
            F.max("timestamp").alias("max_ts"),
            F.collect_set("symbol").alias("symbols")
        ).collect()
        
        batch_min_ts = row_metadata[0]["min_ts"]
        batch_max_ts = row_metadata[0]["max_ts"]
        active_symbols = row_metadata[0]["symbols"]
        
        if batch_min_ts is None: return
    except:
        return

    results_to_write_es = []

    # ---------------------------------------------------------
    # MAIN LOOP: PROCESS EACH TIMEFRAME INDEPENDENTLY
    # ---------------------------------------------------------
    for tf_label, tf_config in TIMEFRAMES.items():
        try:
            tf_duration = tf_config["duration"]
            tf_minutes = tf_config["minutes"]
            
            # --- A. LOAD SPECIFIC TIMEFRAME HISTORY ---
            # Instead of reading /1m and resampling, we read /5m, /1h directly
            tf_hdfs_path = f"{HDFS_BASE_PATH}/{tf_label}"
            lookback_ts = batch_min_ts - pd.Timedelta(days=LOOKBACK_DAYS)
            
            # 1. Read History from Timeframe Folder
            try:
                df_history = spark.read.parquet(tf_hdfs_path) \
                    .filter(F.col("symbol").isin(active_symbols)) \
                    .filter(F.col("timestamp") >= lookback_ts) \
                    # Crucial: Filter OUT any data that might overlap with current batch
                    .filter(F.col("timestamp") < batch_min_ts) \
                    .select("symbol", "timestamp", "open", "high", "low", "close", "volume")
            except:
                # Folder might not exist yet (first run)
                df_history = spark.createDataFrame([], schema=df_batch.select("symbol", "timestamp", "open", "high", "low", "close", "volume").schema)

            # 2. Resample NEW Data to Match Timeframe
            # The batch is always 1m data. We must resample it to 5m/1h before unioning.
            df_new_resampled = (
                df_batch
                .groupBy("symbol", F.window("timestamp", tf_duration))
                .agg(
                    F.first("open").alias("open"), 
                    F.max("high").alias("high"),
                    F.min("low").alias("low"), 
                    F.last("close").alias("close"),
                    F.sum("volume").alias("volume")
                )
                .withColumn("timestamp", F.col("window.end"))
                .drop("window")
            )

            # 3. Combine History + New Resampled Data
            df_full_context = df_history.unionByName(
                df_new_resampled, allowMissingColumns=True
            ).dropDuplicates(["symbol", "timestamp"])

            # --- B. CALCULATE INDICATORS ---
            df_calculated = df_full_context.groupBy("symbol").applyInPandas(
                calculate_all_indicators_udf, schema=output_schema
            )
            
            # Add Timeframe Label
            df_calculated = df_calculated.withColumn("timeframe", F.lit(tf_label))

            # --- C. PREPARE ES WRITE (Real-time) ---
            # Only send updates for timestamps that are "fresh" (>= batch start)
            # Note: For 1h candle, this update will happen every minute, changing the "live" 1h candle.
            df_new_results = df_calculated.filter(F.col("timestamp") >= batch_min_ts)
            if not df_new_results.isEmpty():
                results_to_write_es.append(df_new_results)

            # --- D. HDFS WRITE (Closed Candles Only) ---
            if tf_label != "1m":
                latest_ts_seconds = batch_max_ts.timestamp()
                interval_seconds = tf_minutes * 60
                
                # Check if this minute COMPLETED the timeframe window
                if (latest_ts_seconds + 60) % interval_seconds == 0:
                    print(f"[DEBUG] {tf_label} candle closed. Writing to {tf_hdfs_path}...", flush=True)
                    
                    target_ts = batch_max_ts + pd.Timedelta(minutes=1)
                    df_closed_candle = df_calculated.filter(F.col("timestamp") == target_ts)
                    
                    if not df_closed_candle.isEmpty():
                        # We only save the RAW columns (O/H/L/C/V) to HDFS history to save space
                        # The indicators are re-calculated on load anyway.
                        df_closed_candle.select("symbol", "timestamp", "open", "high", "low", "close", "volume") \
                            .write.mode("append").partitionBy("symbol").parquet(tf_hdfs_path)

        except Exception as e:
            print(f"[ERROR] Processing {tf_label}: {e}")
            # traceback.print_exc()

    # ---------------------------------------------------------
    # E. WRITE TO ELASTICSEARCH
    # ---------------------------------------------------------
    if results_to_write_es:
        try:
            df_final = reduce(DataFrame.union, results_to_write_es)
            df_final = df_final.withColumn("doc_id", F.concat_ws("_", F.col("symbol"), F.col("timeframe"), F.col("timestamp").cast("string")))
            df_final = df_final.withColumn("@timestamp", F.current_timestamp())
            
            writer = (df_final.write
                .format("org.elasticsearch.spark.sql")
                .option("es.nodes", ES_HOST).option("es.port", ES_PORT)
                .option("es.nodes.wan.only", "true").option("es.mapping.id", "doc_id") 
                .option("es.write.operation", "upsert")
                .option("es.net.http.auth.user", ES_USER).option("es.net.http.auth.pass", ES_PASS)
                .option("es.net.ssl", "true")
            )
            if ES_TRUSTSTORE_FILE:
                writer = writer.option("es.net.ssl.truststore.location", ES_TRUSTSTORE_URI).option("es.net.ssl.truststore.pass", ES_TRUSTSTORE_PASS)
            else:
                writer = writer.option("es.net.ssl.cert.allow.self.signed", "true")
            
            writer.mode("append").save(ES_INDEX)
        except Exception as e:
            print(f"[ERROR] ES Write: {e}")

    # ---------------------------------------------------------
    # F. WRITE RAW 1M DATA (Source of Truth)
    # ---------------------------------------------------------
    try:
        (df_batch
         .withColumn("date", F.to_date("timestamp"))
         .coalesce(1)
         .write.mode("append").partitionBy("symbol", "date")
         .parquet(f"{HDFS_BASE_PATH}/1m")
        )
    except Exception as e:
        print(f"[ERROR] HDFS 1m Archive: {e}")

    df_batch.unpersist()
    print(f">>> [BATCH {batch_id}] DONE.\n", flush=True)

# =========================================================
# 6. STREAM START
# =========================================================
df_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
    .option("subscribe", KAFKA_TOPIC)
    .option("startingOffsets", "latest")
    .load()
    .select(F.from_json(F.col("value").cast("string"), input_schema).alias("data"))
    .select("data.*")
    .withColumn("timestamp", (F.col("timestamp_ms") / 1000).cast("timestamp"))
    .drop("timestamp_ms", "@timestamp", "exchange")
)

query = (
    df_stream.writeStream
    .foreachBatch(process_batch)
    .option("checkpointLocation", CHECKPOINT_DIR)
    .trigger(processingTime="1 minute") 
    .start()
)

print("[INFO] Stream started...", flush=True)
query.awaitTermination()