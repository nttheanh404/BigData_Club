#!/bin/bash
set -e

echo "[INFO] Checking Elasticsearch & Kibana..."

export ES_JAVA_HOME=$(/usr/libexec/java_home -v 17)
export JAVA_HOME=$ES_JAVA_HOME

# Check if Elasticsearch is running
if curl -s http://localhost:9200 >/dev/null 2>&1; then
  echo "[INFO] Elasticsearch is already running."
else
  echo "[INFO] Starting new Elasticsearch instance..."
  mkdir -p ../logs
  elasticsearch -E xpack.security.enabled=false -E xpack.ml.enabled=false > ../logs/elasticsearch.log 2>&1 &
  echo "[INFO] Waiting for Elasticsearch to start..."
  for i in {1..60}; do
    if curl -s http://localhost:9200 >/dev/null 2>&1; then
      echo "[INFO] Elasticsearch is up!"
      break
    fi
    sleep 2
  done
  if ! curl -s http://localhost:9200 >/dev/null 2>&1; then
    echo "[ERROR] Elasticsearch failed to start!"
    exit 1
  fi
fi

# Start Kibana
if pgrep -x "kibana" >/dev/null; then
  echo "[INFO] Kibana already running."
else
  echo "[INFO] Starting Kibana..."
  kibana > ../logs/kibana.log 2>&1 &
  echo "[INFO] Kibana started successfully! (check logs/kibana.log)"
fi