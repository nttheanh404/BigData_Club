"""
Service: batch_processor.py
----------------------------
Process historical OHLCV data and train predictive model.

Steps:
  1. Load historical CSVs from data/historical/
  2. Compute features (returns, MA, volatility)
  3. Create binary label (1 if price ↑ next n minutes)
  4. Train XGBoost model
  5. Save trained model and scaler to models/

Author: Mysorf
"""

import os
import glob
import pickle
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# === Paths ===
DATA_DIR = os.getenv("DATA_DIR", "../data/historical")
MODEL_DIR = os.getenv("MODEL_DIR", "../models")
os.makedirs(MODEL_DIR, exist_ok=True)

# === Parameters ===
TARGET_SHIFT = int(os.getenv("TARGET_SHIFT", "5"))  # predict next 5 candles
TEST_SIZE = float(os.getenv("TEST_SIZE", "0.2"))


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
  """Compute simple features from OHLCV."""
  df["close"] = df["close"].astype(float)
  df["returns"] = df["close"].pct_change()
  df["ma_5"] = df["close"].rolling(5).mean()
  df["ma_20"] = df["close"].rolling(20).mean()
  df["volatility"] = df["returns"].rolling(10).std()
  df.dropna(inplace=True)
  return df


def create_label(df: pd.DataFrame, shift: int) -> pd.DataFrame:
  """Create binary label: 1 if next close > current close."""
  df["future_close"] = df["close"].shift(-shift)
  df["target"] = (df["future_close"] > df["close"]).astype(int)
  df.dropna(inplace=True)
  return df


def load_all_data() -> pd.DataFrame:
  files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
  print(DATA_DIR)
  if not files:
    raise FileNotFoundError(f"No CSV files found in {DATA_DIR}")

  dfs = []
  for f in files:
    try:
      df = pd.read_csv(f)
      if "open_time" in df.columns:
        df = df.rename(columns={"open_time": "timestamp"})

      required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
      missing = [c for c in required_cols if c not in df.columns]
      if missing:
        print(f"[WARN] {f} missing {missing}, skipped.")
        continue

      if not str(df["timestamp"].iloc[0]).isdigit():
        df["timestamp"] = pd.to_datetime(df["timestamp"]).astype(int) // 10 ** 6

      df["symbol"] = df.get("symbol", os.path.basename(f).split("_")[0])
      df = df[required_cols + ["symbol"]]

      dfs.append(df)
    except Exception as e:
      print(f"[ERROR] Failed to load {f}: {e}")

  if not dfs:
    raise ValueError("No valid data to concatenate")

  full_df = pd.concat(dfs, ignore_index=True)
  print(f"[INFO] Loaded {len(full_df)} rows from {len(files)} CSV files.")
  return full_df


def main():
  print("=== [BATCH PROCESSOR] Start training pipeline ===")

  df = load_all_data()
  print(f"[INFO] Loaded {len(df)} rows from {DATA_DIR}")

  df = compute_features(df)
  df = create_label(df, TARGET_SHIFT)
  features = ["returns", "ma_5", "ma_20", "volatility"]

  X = df[features].values
  y = df["target"].values

  scaler = StandardScaler()
  X_scaled = scaler.fit_transform(X)

  X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=TEST_SIZE, shuffle=False)

  model = XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, subsample=0.8)
  model.fit(X_train, y_train)

  acc = model.score(X_test, y_test)
  print(f"Model trained successfully. Test accuracy = {acc:.4f}")

  with open(os.path.join(MODEL_DIR, "xgb_model.pkl"), "wb") as f:
    pickle.dump(model, f)
  with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
    pickle.dump(scaler, f)

  print(f"Model and scaler saved to {MODEL_DIR}/")


if __name__ == "__main__":
  main()