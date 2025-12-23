"""
Service: historical_crawler.py
-------------------------------
Crawl historical OHLCV data from Binance REST API.
"""

import os
import requests
import pandas as pd
from dotenv import load_dotenv

# Load environment
load_dotenv()

SYMBOLS = [s.strip().upper() for s in os.getenv("CRYPTO_SYMBOLS", "BTC/USDT,ETH/USDT").split(",")]
INTERVAL = os.getenv("CRAWL_INTERVAL", "1m")
LIMIT = int(os.getenv("CRAWL_LIMIT", "1000"))
API_BASE = "https://api.binance.com/api/v3/klines"


def fetch_binance_ohlcv(symbol: str, interval: str = "1m", limit: int = 100):
  """
  Fetch OHLCV data from Binance API.
  """
  pair = symbol.replace("/", "")
  params = {"symbol": pair, "interval": interval, "limit": limit}

  print(f"[INFO] Fetching {symbol} ({interval}, limit={limit})...")
  r = requests.get(API_BASE, params=params, timeout=10)
  r.raise_for_status()

  data = r.json()
  df = pd.DataFrame(data, columns=[
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "num_trades",
    "taker_buy_base", "taker_buy_quote", "ignore"
  ])

  df["symbol"] = symbol
  df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
  df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

  return df


def main():
  for symbol in SYMBOLS:
    try:
      df = fetch_binance_ohlcv(symbol, INTERVAL, LIMIT)
      print(df.head())  # Check
      print(f"[SUCCESS] {symbol}: {len(df)} rows fetched.\n")
    except Exception as e:
      print(f"[ERROR] Failed to fetch {symbol}: {e}")


if __name__ == "__main__":
  main()
