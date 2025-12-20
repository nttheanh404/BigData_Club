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

# HDFS Configs
HDFS_RAW_PATH = get_env("HDFS_RAW_PATH", "hdfs://hdfs-service:9000/data/crypto/raw_1m")
CHECKPOINT_DIR = get_env("CHECKPOINT_DIR", "hdfs://hdfs-service:9000/data/crypto/checkpoints")
LOOKBACK_DAYS = int(get_env("LOOKBACK_DAYS", "5")) 

# Elasticsearch Connection
ES_HOST = get_env("ES_HOST", "elasticsearch")
ES_PORT = get_env("ES_PORT", "9200")
ES_USER = get_env("ES_USER", "elastic")
ES_PASS = get_env("ES_PASS", "changeme")

# --- TRUSTSTORE HANDLING (CRITICAL FIX) ---
# Spark (Java) needs "file:///path", but Python needs "/path"
ES_TRUSTSTORE_URI = get_env("ES_SSL_TRUSTSTORE_PATH", "") 
ES_TRUSTSTORE_FILE = ES_TRUSTSTORE_URI.replace("file://", "") if ES_TRUSTSTORE_URI else None
ES_TRUSTSTORE_PASS = get_env("ES_SSL_TRUSTSTORE_PASS", "changeit")

ES_INDEX = get_env("ES_INDEX", "crypto_technical_analysis").split("/")[0]

TIMEFRAMES = {
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "1h": "1 hour",
    "4h": "4 hours"
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
print(f"[INIT] HDFS: {HDFS_RAW_PATH}", flush=True)

# Validate Truststore before starting
if ES_TRUSTSTORE_FILE:
    if os.path.exists(ES_TRUSTSTORE_FILE):
        print(f"[INIT] SUCCESS: Found Truststore at {ES_TRUSTSTORE_FILE}", flush=True)
    else:
        print(f"[INIT] ERROR: Truststore NOT found at {ES_TRUSTSTORE_FILE}", flush=True)

spark = (
    SparkSession.builder
    .appName("CryptoMultiFrameProcessor")
    .config("spark.hadoop.fs.defaultFS", "hdfs://hdfs-service:9000")
    .config("spark.sql.execution.arrow.pyspark.enabled", "false")
    .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
    .config("spark.hadoop.dfs.replication", "1")
    .config("spark.hadoop.dfs.client.use.datanode.hostname", "true")
    .config("spark.network.timeout", "60s")
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

    print(f"\n>>> [BATCH {batch_id}] STARTING...", flush=True)
    df_batch.cache()

    # --- STEP 1: WRITE RAW ---
    print(f"[DEBUG] {batch_id}: Step 1 - Writing to HDFS...", flush=True)
    try:
        (df_batch
         .withColumn("date", F.to_date("timestamp"))
         .write.mode("append").partitionBy("symbol", "date").parquet(HDFS_RAW_PATH)
        )
        print(f"[DEBUG] {batch_id}: Step 1 - DONE", flush=True)
    except Exception as e:
        print(f"!!! [WARN] {batch_id}: HDFS Write Failed: {e}", flush=True)

    print(f"[DEBUG] {batch_id}: Waiting 5s for HDFS consistency...", flush=True)
    time.sleep(5)

    # --- STEP 2: PREPARE CONTEXT ---
    print(f"[DEBUG] {batch_id}: Step 2 - Reading History...", flush=True)
    try:
        # Check metadata
        batch_min_ts = df_batch.agg(F.min("timestamp")).collect()[0][0]
        if batch_min_ts is None:
             print("[ERROR] Batch Timestamp is NULL!", flush=True)
             return
        
        lookback_ts = batch_min_ts - pd.Timedelta(days=LOOKBACK_DAYS)
        active_symbols = [r.symbol for r in df_batch.select("symbol").distinct().collect()]

        try:
            # Read History
            df_history = spark.read.parquet(HDFS_RAW_PATH)
            df_history_filtered = (
                df_history
                .filter(F.col("symbol").isin(active_symbols))
                .filter(F.col("timestamp") >= lookback_ts)
                .select("symbol", "timestamp", "open", "high", "low", "close", "volume")
            )
            df_full_context = df_history_filtered.unionByName(
                df_batch.select("symbol", "timestamp", "open", "high", "low", "close", "volume"), 
                allowMissingColumns=True
            ).dropDuplicates(["symbol", "timestamp"])
            
            # Verify read
            #  count = df_full_context.count()
            print(f"[DEBUG] {batch_id}: Step 2 - DONE. Rows: {count}", flush=True)
        except Exception as e:
            print(f"!!! [WARN] {batch_id}: HDFS Read Failed (First Run?). Using Batch Only.", flush=True)
            df_full_context = df_batch.select("symbol", "timestamp", "open", "high", "low", "close", "volume")

    except Exception as e:
        print(f"[ERROR] Step 2 Critical: {e}", flush=True)
        return

    results_to_write = []

    # --- STEP 3: CALCULATE ---
    print(f"[DEBUG] {batch_id}: Step 3 - Calculating...", flush=True)
    try:
        for tf_label, tf_duration in TIMEFRAMES.items():
            df_resampled = (
                df_full_context
                .groupBy("symbol", F.window("timestamp", tf_duration))
                .agg(
                    F.first("open").alias("open"), F.max("high").alias("high"),
                    F.min("low").alias("low"), F.last("close").alias("close"),
                    F.sum("volume").alias("volume")
                )
                .withColumn("timestamp", F.col("window.end"))
                .withColumn("timeframe", F.lit(tf_label))
                .drop("window")
            )
            df_calculated = df_resampled.groupBy("symbol").applyInPandas(calculate_all_indicators_udf, schema=output_schema)
            df_new = df_calculated.filter(F.col("timestamp") >= batch_min_ts)
            if not df_new.isEmpty(): results_to_write.append(df_new)
        print(f"[DEBUG] {batch_id}: Step 3 - DONE", flush=True)
    except Exception as e:
        print(f"!!! [ERROR] Calculation Failed: {e}", flush=True)
        traceback.print_exc()
        return

    # --- STEP 4: WRITE TO ES ---
    if results_to_write:
        print(f"[DEBUG] {batch_id}: Step 4 - Writing to ES...", flush=True)
        try:
            df_final = reduce(DataFrame.union, results_to_write)
            df_final = df_final.withColumn("doc_id", F.concat_ws("_", F.col("symbol"), F.col("timeframe"), F.col("timestamp").cast("string")))
            df_final = df_final.withColumn("@timestamp", F.current_timestamp())
            
            # --- CONFIGURE WRITER ---
            writer = (df_final.write
             .format("org.elasticsearch.spark.sql")
             .option("es.nodes", ES_HOST)
             .option("es.port", ES_PORT)
             .option("es.nodes.wan.only", "true")
             .option("es.mapping.id", "doc_id") 
             .option("es.write.operation", "upsert")
             .option("es.net.http.auth.user", ES_USER)
             .option("es.net.http.auth.pass", ES_PASS)
             .option("es.net.ssl", "true")
            )
            
            # Use URI for Spark/Java config (file:///...)
            if ES_TRUSTSTORE_FILE and os.path.exists(ES_TRUSTSTORE_FILE):
                print(f"[DEBUG] Configuring SSL Truststore: {ES_TRUSTSTORE_URI}", flush=True)
                writer = writer.option("es.net.ssl.truststore.location", ES_TRUSTSTORE_URI)
                writer = writer.option("es.net.ssl.truststore.pass", ES_TRUSTSTORE_PASS)
            else:
                print("[WARN] Truststore not found. Allowing Self-Signed Certs.", flush=True)
                writer = writer.option("es.net.ssl.cert.allow.self.signed", "true")

            writer.mode("append").save(ES_INDEX)
            
            print(f"[DEBUG] {batch_id}: Step 4 - DONE. SUCCESS.", flush=True)
        except Exception as e:
            print(f"!!! [ERROR] ES Write Failed: {e}", flush=True)
    else:
        print(f">>> [BATCH {batch_id}] COMPLETED (No new data)", flush=True)
    
    df_batch.unpersist()

# =========================================================
# 6. STREAM DEFINITION
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

print("[INFO] Stream started... Waiting for data...", flush=True)
query.awaitTermination()
