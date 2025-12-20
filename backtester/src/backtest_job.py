import sys
import argparse
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession
import pyspark.sql.functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType

# --- CONFIG ---
# Default to internal HDFS service URL
DEFAULT_HDFS = "hdfs://hdfs-service:9000/data/crypto/raw_1m"

def calculate_strategy(pdf, rsi_lower, rsi_upper):
    """
    Runs on every symbol independently.
    Simulates buying when RSI < lower and selling when RSI > upper.
    """
    # 1. Sort by time to ensure chronological order
    pdf = pdf.sort_values("timestamp")
    close = pdf["close"]
    
    # 2. Calculate RSI (Vectorized implementation for speed)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    pdf["rsi"] = 100 - (100 / (1 + rs))
    
    # 3. Simulation Loop
    initial_capital = 1000.0
    balance = initial_capital
    position = 0.0 
    trades = 0
    wins = 0
    entry_price = 0.0
    
    # Iterate through history
    for i, row in pdf.iterrows():
        rsi = row["rsi"]
        price = row["close"]
        
        if np.isnan(rsi): continue
        
        # BUY SIGNAL
        if rsi < rsi_lower and position == 0:
            position = balance / price
            balance = 0
            entry_price = price
            
        # SELL SIGNAL
        elif rsi > rsi_upper and position > 0:
            exit_price = price
            balance = position * exit_price
            trades += 1
            if exit_price > entry_price:
                wins += 1
            position = 0

    # Mark to Market (Sell remaining position at last price)
    if position > 0:
        balance = position * pdf.iloc[-1]["close"]
    
    # Calculate Metrics
    total_return = ((balance - initial_capital) / initial_capital) * 100
    win_rate = (wins / trades * 100) if trades > 0 else 0.0
    
    return pd.DataFrame([{
        "symbol": pdf.iloc[0]["symbol"],
        "trades": trades,
        "win_rate": win_rate,
        "final_balance": balance,
        "return_pct": total_return
    }])

# --- SCHEMA ---
result_schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("trades", IntegerType(), True),
    StructField("win_rate", DoubleType(), True),
    StructField("final_balance", DoubleType(), True),
    StructField("return_pct", DoubleType(), True)
])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdfs", default=DEFAULT_HDFS)
    parser.add_argument("--rsi_lower", type=int, default=30)
    parser.add_argument("--rsi_upper", type=int, default=70)
    args = parser.parse_args()

    spark = SparkSession.builder.appName("CryptoBacktester").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    
    print(f"\n>>> [JOB START] RSI Strategy: Buy<{args.rsi_lower} | Sell>{args.rsi_upper}")
    
    try:
        # Read Parquet from HDFS
        df = spark.read.parquet(args.hdfs)
        
        # Select minimum columns to reduce I/O
        df_clean = df.select("symbol", "timestamp", "close")
        
        # Define wrapper for UDF to pass arguments
        def strategy_wrapper(pdf):
            return calculate_strategy(pdf, args.rsi_lower, args.rsi_upper)
        
        # Run Distributed Backtest
        results = df_clean.groupBy("symbol").applyInPandas(strategy_wrapper, schema=result_schema)
        
        # Collect top results to Driver
        top_performers = results.orderBy(F.col("return_pct").desc()).limit(20).toPandas()
        
        print("\n>>> RESULTS (Top 20):")
        print(top_performers.to_string(index=False))
        
        # Optional: Save results back to HDFS/Elasticsearch here
        
    except Exception as e:
        print(f"[ERROR] Backtest Failed: {e}")
    
    spark.stop()
