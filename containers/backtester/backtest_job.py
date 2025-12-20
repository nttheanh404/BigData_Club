import argparse
import pandas as pd
import numpy as np
import os
import hashlib
from datetime import datetime

from pyspark.sql import SparkSession
import pyspark.sql.functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, IntegerType
)

# ================= Schema =================
result_schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("trades", IntegerType(), True),
    StructField("win_rate", DoubleType(), True),
    StructField("final_balance", DoubleType(), True),
    StructField("return_pct", DoubleType(), True)
])

# ================= Backtest Logic =================
def run_simulation(pdf, rsi_low, rsi_high):
    if pdf.empty:
        return pd.DataFrame(columns=[f.name for f in result_schema.fields])

    pdf = pdf.sort_values("timestamp")
    close = pdf["close"]

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    pdf["rsi"] = 100 - (100 / (1 + rs))

    balance, position = 1000.0, 0.0
    trades, wins, entry_price = 0, 0, 0.0

    for _, row in pdf.iterrows():
        rsi, price = row["rsi"], row["close"]
        if np.isnan(rsi):
            continue

        if rsi < rsi_low and position == 0:
            position = balance / price
            balance = 0
            entry_price = price

        elif rsi > rsi_high and position > 0:
            balance = position * price
            trades += 1
            if price > entry_price:
                wins += 1
            position = 0

    if position > 0:
        balance = position * pdf.iloc[-1]["close"]

    return pd.DataFrame([{
        "symbol": pdf.iloc[-1]["symbol"],
        "trades": trades,
        "win_rate": (wins / trades * 100) if trades > 0 else 0.0,
        "final_balance": float(balance),
        "return_pct": ((balance - 1000.0) / 1000.0) * 100
    }])

# ================= Main =================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdfs_path", required=True)
    parser.add_argument("--rsi_low", type=int, required=True)
    parser.add_argument("--rsi_high", type=int, required=True)
    parser.add_argument("--job_id", required=True)
    args = parser.parse_args()

    spark = (
        SparkSession.builder
        .appName("HistoricalBacktester")
        .getOrCreate()
    )

    try:
        df = spark.read.parquet(args.hdfs_path)

        results = df.groupBy("symbol").applyInPandas(
            lambda pdf: run_simulation(pdf, args.rsi_low, args.rsi_high),
            schema=result_schema
        )

        final_df = (
            results
            .withColumn("job_id", F.lit(args.job_id))
            .withColumn("created_at", F.current_timestamp())
        )

        # ========= Save CSV to HDFS =========
        final_df.coalesce(1).write.mode("overwrite").csv(
            f"hdfs://hdfs-service:9000/reports/{args.job_id}"
        )

        # ========= Elasticsearch =========
        es_options = {
            "es.nodes": os.getenv("ES_HOST"),
            "es.port": "9200",
            "es.net.http.auth.user": os.getenv("ES_USER"),
            "es.net.http.auth.pass": os.getenv("ES_PASS"),
            "es.nodes.wan.only": "false",

            "es.net.ssl": "true",
            "es.net.ssl.truststore.location": os.getenv("ES_SSL_TRUSTSTORE_PATH"),
            "es.net.ssl.truststore.pass": os.getenv("ES_SSL_TRUSTSTORE_PASS"),
        }

        final_df.write \
            .format("org.elasticsearch.spark.sql") \
            .options(**es_options) \
            .mode("append") \
            .save("backtest_results")

    finally:
        spark.stop()

