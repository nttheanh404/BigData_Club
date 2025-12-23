import os
import warnings
import traceback
from datetime import datetime, timedelta, date
import pandas as pd
import numpy as np
from functools import reduce

from pyspark.sql import SparkSession, DataFrame
import pyspark.sql.functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, TimestampType, LongType, DateType
)
from pyspark.sql import DataFrame, Window
warnings.filterwarnings("ignore")

# =========================================================
# LOG HELPER
# =========================================================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# =========================================================
# 1. CONFIGURATION
# =========================================================
def get_env(key, default=None):
    val = os.getenv(key, default)
    if val is None:
        log(f"[WARN] Env var {key} not found, using default: {default}")
    return val

KAFKA_BOOTSTRAP = get_env("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_TOPIC = get_env("KAFKA_TOPIC", "crypto_ohlcv_1m")
HDFS_BASE_PATH = get_env("HDFS_BASE_PATH", "hdfs://hdfs-service:9000/data/crypto")
CHECKPOINT_DIR = get_env("CHECKPOINT_DIR", "hdfs://hdfs-service:9000/data/checkpoints/crypto_stream")
LOOKBACK_DAYS = int(get_env("LOOKBACK_DAYS", "5"))
from datetime import timedelta
ES_HOST = get_env("ES_HOST", "elasticsearch")
ES_PORT = get_env("ES_PORT", "9200")
ES_USER = get_env("ES_USER", "elastic")
ES_PASS = get_env("ES_PASS", "changeme")
ES_INDEX = get_env("ES_INDEX", "crypto_technical_analysis").split("/")[0]


ES_TRUSTSTORE_URI = get_env("ES_SSL_TRUSTSTORE_PATH", "") 
ES_TRUSTSTORE_FILE = ES_TRUSTSTORE_URI.replace("file://", "") if ES_TRUSTSTORE_URI else None
ES_TRUSTSTORE_PASS = get_env("ES_SSL_TRUSTSTORE_PASS", "changeit")


# Định nghĩa các khung thời gian cần tính toán
TIMEFRAMES = {
    "1m":  {"duration": "1 minute"},
    "5m":  {"duration": "5 minutes"},
    "15m": {"duration": "15 minutes"},
    "1h":  {"duration": "1 hour"},
    "4h":  {"duration": "4 hours"}
}

# =========================================================
# 2. SCHEMAS
# =========================================================
# Schema đầu vào từ Kafka
input_schema = StructType([
    StructField("symbol", StringType()),
    StructField("exchange", StringType()),
    StructField("timestamp_ms", LongType()),
    StructField("@timestamp", StringType()),
    StructField("open", DoubleType()),
    StructField("high", DoubleType()),
    StructField("low", DoubleType()),
    StructField("close", DoubleType()),
    StructField("volume", DoubleType()),
])

# Schema tối giản để đọc lịch sử từ HDFS (chỉ cần OHLCV)
history_schema = StructType([
    StructField("symbol", StringType()),
    StructField("timestamp", TimestampType()),
    StructField("open", DoubleType()),
    StructField("high", DoubleType()),
    StructField("low", DoubleType()),
    StructField("close", DoubleType()),
    StructField("volume", DoubleType())
])

# Schema đầu ra sau khi tính toán (chứa các Indicators)
output_schema = StructType([
    StructField("symbol", StringType()),
    StructField("timestamp", TimestampType()),
    StructField("open", DoubleType()),
    StructField("high", DoubleType()),
    StructField("low", DoubleType()),
    StructField("close", DoubleType()),
    StructField("volume", DoubleType()),
    StructField("ema_9", DoubleType()),
    StructField("ema_20", DoubleType()),
    StructField("ema_50", DoubleType()),
    StructField("ema_200", DoubleType()),
    StructField("macd_line", DoubleType()),
    StructField("macd_signal", DoubleType()),
    StructField("macd_hist", DoubleType()),
    StructField("rsi_14", DoubleType()),
    StructField("stoch_k", DoubleType()),
    StructField("stoch_d", DoubleType()),
    StructField("bb_upper", DoubleType()),
    StructField("bb_middle", DoubleType()),
    StructField("bb_lower", DoubleType()),
    StructField("atr_14", DoubleType()),
    StructField("obv", DoubleType()),
  ])

# =========================================================
# 3. SPARK INIT
# =========================================================
spark = (
    SparkSession.builder
    .appName("CryptoProcessor_Resampled_Fixed")
    .config("spark.hadoop.fs.defaultFS", "hdfs://hdfs-service:9000")
    .config("spark.sql.execution.arrow.pyspark.enabled", "true")
    .config("spark.network.timeout", "120s")
    .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
    # Tắt kiểm tra strict SSL để debug nhanh
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

# =========================================================
# 4. INDICATOR LOGIC (PANDAS UDF)
# =========================================================
def calculate_all_indicators_udf(pdf: pd.DataFrame) -> pd.DataFrame:
    if pdf.empty: return pdf
    
    # Sắp xếp theo thời gian là bắt buộc
    pdf = pdf.sort_values("timestamp")
    
    # Tạo biến tạm để tính toán nhanh hơn
    close = pdf["close"]
    high = pdf["high"]
    low = pdf["low"]
    volume = pdf["volume"]

    # --- Indicators ---
    pdf["ema_9"] = close.ewm(span=9, adjust=False).mean()
    pdf["ema_20"] = close.ewm(span=20, adjust=False).mean()
    pdf["ema_50"] = close.ewm(span=50, adjust=False).mean()
    pdf["ema_200"] = close.ewm(span=200, adjust=False).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    pdf["macd_line"] = ema12 - ema26
    pdf["macd_signal"] = pdf["macd_line"].ewm(span=9, adjust=False).mean()
    pdf["macd_hist"] = pdf["macd_line"] - pdf["macd_signal"]

    delta = close.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    pdf["rsi_14"] = 100 - (100 / (1 + rs))

    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    pdf["stoch_k"] = 100 * (close - low14) / (high14 - low14 + 1e-9)
    pdf["stoch_d"] = pdf["stoch_k"].rolling(3).mean()

    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    pdf["bb_middle"] = mid
    pdf["bb_upper"] = mid + 2 * std
    pdf["bb_lower"] = mid - 2 * std

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    pdf["atr_14"] = tr.rolling(14).mean()

    pdf["obv"] = (volume * np.sign(close.diff()).fillna(0)).cumsum()
    
    # Fill NA để tránh lỗi khi ghi Parquet/ES
    return pdf.fillna(0.0)
def hdfs_path_exists(path: str) -> bool:
    try:
        sc = spark.sparkContext
        conf = sc._jsc.hadoopConfiguration()
        pt = sc._jvm.org.apache.hadoop.fs.Path(path)
        
        # KEY FIX: Ask specifically for the FileSystem that owns this path
        fs = pt.getFileSystem(conf) 
        
        return fs.exists(pt)
    except Exception as e:
        # Log the specific error to help debug if it persists
        print(f"Error checking HDFS path '{path}': {e}")
        return False
# =========================================================
# 5. FOREACH BATCH STRATEGY
# =========================================================
def process_batch(df_batch: DataFrame, batch_id: int):
    log(f">>> [BATCH {batch_id}] ENTER")

    # Step 0: Clean symbol names
    df_batch = df_batch.withColumn("symbol", F.regexp_replace("symbol", "[^a-zA-Z0-9]", ""))

    # Step 1: Metadata extraction
    meta = df_batch.agg(
        F.min("timestamp").alias("min_ts"),
        F.collect_set("symbol").alias("symbols")
    ).collect()
    
    batch_min_ts = meta[0]["min_ts"]
    symbols = meta[0]["symbols"]

    if not batch_min_ts:
        log("Batch empty → RETURN")
        return

    # Define lookback window (e.g., 300 minutes for MA200 on 1m chart)
    lookback_ts = batch_min_ts - timedelta(minutes=300)
    tf_path_1m = f"{HDFS_BASE_PATH}/1m"

    # Step 2: Read historical 1m data (FIXED)
    df_history_1m = spark.createDataFrame([], history_schema) # Default empty
    
    try:
        # Calculate target dates for partition pruning
        days_needed = (batch_min_ts.date() - lookback_ts.date()).days + 1
        target_dates = [lookback_ts.date() + timedelta(days=x) for x in range(days_needed)]
        # Convert to strings matching HDFS partition format (YYYY-MM-DD)
        target_date_strs = [str(d) for d in target_dates if d <= datetime.now().date()]
        
        # Check if root path exists to prevent crash on very first run
        if hdfs_path_exists(tf_path_1m):
            log(f"Reading History from root: {tf_path_1m} for dates: {target_date_strs}")
            
            df_history_1m = (
                spark.read
                .option("basePath", tf_path_1m)  # Vital for partition discovery
                .schema(history_schema)
                .parquet(tf_path_1m)             # Point to ROOT, not subfolders
                .filter(F.col("date").isin(target_date_strs)) # Spark picks only these folders
                .filter(F.col("symbol").isin(symbols))
                .filter(F.col("timestamp") < batch_min_ts)
            )
        else:
            log("History root path not found (First run?)")

    except Exception as e:
        log(f"[WARNING] History read failed: {e}")
        df_history_1m = spark.createDataFrame([], history_schema)

    # Step 3: Combine history + batch
    cols_needed = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
    
    # Ensure columns exist before selecting (handle schema mismatch gracefully)
    try:
        df_full_1m = df_history_1m.select(cols_needed).unionByName(df_batch.select(cols_needed))
    except Exception as e:
         log(f"[ERROR] Union failed (Schema mismatch?): {e}")
         # Fallback: Process batch only (indicators will be null but won't crash)
         df_full_1m = df_batch.select(cols_needed)

    df_full_1m = df_full_1m.orderBy("timestamp")

    # Step 4: Keep last 300 rows per symbol (Simplified for performance)
    # Using window function to rank is safer than global sort+limit for multi-symbol batches
    window_spec = F.window("timestamp", "1000 hours") 
    full_count = df_full_1m.count()
    
    if full_count > 300 * len(symbols):
        # Optimisation: Keep only the tail end
        df_full_1m = (df_full_1m
                      .withColumn("rn", F.row_number().over(
                          Window.partitionBy("symbol").orderBy(F.col("timestamp").desc())
                      ))
                      .filter(F.col("rn") <= 300)
                      .drop("rn")
                      .orderBy("timestamp"))

    # Debug Logging
    row_count = df_full_1m.count()
    if row_count > 0:
        min_ts = df_full_1m.agg(F.min('timestamp')).collect()[0][0]
        max_ts = df_full_1m.agg(F.max('timestamp')).collect()[0][0]
    else:
        min_ts, max_ts = "N/A", "N/A"

    log(f"[INFO] df_full_1m rows: {row_count}")
    log(f"[INFO] Timestamp range: {min_ts} → {max_ts}")
    # df_full_1m.show(5, truncate=False) # Uncomment to debug

    results = []

    # Step 5: Resample & calculate indicators
    for tf, cfg in TIMEFRAMES.items():
        tf_start = datetime.now()
        
        # Resample
        df_resampled = (
            df_full_1m
            .groupBy("symbol", F.window("timestamp", cfg["duration"]))
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

        # Apply Pandas UDF (Indicators)
        df_calc = (
            df_resampled
            .groupBy("symbol")
            .applyInPandas(calculate_all_indicators_udf, output_schema)
            .withColumn("timeframe", F.lit(tf))
        )

        results.append(df_calc)

        elapsed = (datetime.now() - tf_start).total_seconds()
        log(f"TF [{tf}] Calculated via Resample in {elapsed:.2f}s")

    # Step 6: Write to ES
    if results:
        df_final = reduce(DataFrame.union, results)
        df_final = df_final.withColumn("timestamp", F.from_utc_timestamp(F.col("timestamp"), "Asia/Ho_Chi_Minh"))
        df_final = df_final.withColumn("doc_id", F.concat_ws("_", F.col("symbol"), F.col("timeframe"), F.col("timestamp").cast("string")))

        log(f"--- PREVIEW DATA WRITING TO ES ({df_final.count()} rows) ---")
        # df_final.select("doc_id", "symbol", "timeframe", "close", "rsi_14").show(5, truncate=False)

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
                  .option("es.batch.size.entries", "1000"))

        if ES_TRUSTSTORE_FILE and os.path.exists(ES_TRUSTSTORE_FILE):
            writer = writer.option("es.net.ssl.truststore.location", ES_TRUSTSTORE_URI)
            writer = writer.option("es.net.ssl.truststore.pass", ES_TRUSTSTORE_PASS)
        else:
            writer = writer.option("es.net.ssl.cert.allow.self.signed", "true")

        try:
            writer.mode("append").save(ES_INDEX)
            log("WRITE ES DONE")
        except Exception as e:
            log(f"[ERROR] Write to ES failed: {e}")

    # Step 7: Write batch to HDFS 1m (Persist raw data for next loops)
    log("WRITE RAW 1m TO HDFS")
    try:
        (
            df_batch
            .withColumn("date", F.to_date("timestamp"))
            .write
            .mode("append")
            .partitionBy("symbol", "date")
            .parquet(f"{HDFS_BASE_PATH}/1m")
        )
    except Exception as e:
        log(f"[ERROR] HDFS Write failed: {e}")

    log(f">>> [BATCH {batch_id}] DONE SUCCESS")

# =========================================================
# 6. STREAM START
# =========================================================
log("Starting Stream...")
df_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
    .option("subscribe", KAFKA_TOPIC)
    .option("startingOffsets", "latest")
    .option("failOnDataLoss", "false")
    .load()
    .select(F.from_json(F.col("value").cast("string"), input_schema).alias("d"))
    .select("d.*")
    .withColumn("timestamp", (F.col("timestamp_ms") / 1000).cast("timestamp"))
)

query = (
    df_stream.writeStream
    .foreachBatch(process_batch)
    .option("checkpointLocation", CHECKPOINT_DIR)
    .trigger(processingTime="1 minute")
    .start()
)

query.awaitTermination()