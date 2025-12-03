"""
Service: realtime_evaluator.py
------------------------------
Evaluate model predictions in real-time.

Reads prediction results (from Elasticsearch or Kafka),
compares each prediction with the next candle's price,
and computes accuracy metrics in real-time.

Output:
- Realtime stats printed to console.
- Aggregated results stored in Elasticsearch index: crypto_prediction_stats

Author: Mysorf
"""

import os
import time
from elasticsearch import Elasticsearch
from datetime import datetime

# Config
ES_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
ES_PORT = os.getenv("ELASTICSEARCH_PORT", "9200")

ES_PRED_INDEX = os.getenv("ES_PRED_INDEX", "crypto_ohlcv_1m_pred")
ES_STATS_INDEX = os.getenv("ES_STATS_INDEX", "crypto_prediction_stats")

POLL_INTERVAL = int(os.getenv("EVAL_POLL_INTERVAL", "10"))  # seconds

# CLient
es = Elasticsearch([f"http://{ES_HOST}:{ES_PORT}"])

if not es.ping():
  raise ConnectionError(f"❌ Cannot connect to Elasticsearch at {ES_HOST}:{ES_PORT}")

print(f"[INFO] Connected to Elasticsearch: {ES_HOST}:{ES_PORT}")

# Ensure stats index exists
if not es.indices.exists(index=ES_STATS_INDEX):
  es.indices.create(index=ES_STATS_INDEX, ignore=400)
  print(f"[INFO] Created index {ES_STATS_INDEX}")

# State tracker
last_pred = {}  # {symbol: {"ts": ..., "close": ..., "prediction": ...}}
stats = {"total": 0, "correct": 0}


# Main loop
def evaluate_predictions():
  global stats, last_pred

  # Get newest predictions
  res = es.search(
    index=ES_PRED_INDEX,
    size=200,
    sort="@timestamp:desc",
    query={"match_all": {}},
  )

  if "hits" not in res["hits"]:
    print("[WARN] No predictions found yet.")
    return

  hits = res["hits"]["hits"]
  hits.sort(key=lambda h: h["_source"].get("timestamp_ms", 0))  # chronological order

  for hit in hits:
    doc = hit["_source"]
    symbol = doc.get("symbol")
    close_now = doc.get("close")
    ts = doc.get("timestamp_ms")
    pred = doc.get("prediction")

    if not all([symbol, close_now, ts, pred]):
      continue

    prev = last_pred.get(symbol)

    if prev:
      # Evaluate accuracy
      if pred == "UP" and close_now > prev["close"]:
        correct = True
      elif pred == "DOWN" and close_now < prev["close"]:
        correct = True
      else:
        correct = False

      stats["total"] += 1
      if correct:
        stats["correct"] += 1

      accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0

      print(f"[EVAL] {symbol:<8} | pred={pred:<5} | "
            f"prev_close={prev['close']:.2f} → now={close_now:.2f} | "
            f"{'✅' if correct else '❌'} | acc={accuracy:.3f}")

      # Save stat snapshot
      es.index(
        index=ES_STATS_INDEX,
        body={
          "@timestamp": datetime.utcnow().isoformat(),
          "symbol": symbol,
          "accuracy": accuracy,
          "total": stats["total"],
          "correct": stats["correct"],
        },
      )

    # Update last prediction
    last_pred[symbol] = {"ts": ts, "close": close_now, "prediction": pred}


def main():
  print(f"[INFO] Realtime evaluator started (poll={POLL_INTERVAL}s)...")
  while True:
    try:
      evaluate_predictions()
      time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
      print("\n[STOP] Realtime evaluator stopped.")
      break
    except Exception as e:
      print("[ERROR] Evaluation loop:", e)
      time.sleep(5)


if __name__ == "__main__":
  main()