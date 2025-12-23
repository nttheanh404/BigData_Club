# Big Data Crypto – Lambda System

Real-time cryptocurrency analytics system built with **Apache Spark**, **Kafka**, and **Elasticsearch**, following the *
*Lambda Architecture** pattern.

- **Batch Layer:** historical data processing with Spark
- **Speed Layer:** Real-time data processing via Kafka + Spark Streaming
- **Serving Layer:** Display results via Flask + Elasticsearch

---

## Overview

This project implements a **full Lambda Architecture** for analyzing and serving real-time cryptocurrency market data.

### Key Components

| Layer         | Technology                         | Description                                      |
|:--------------|:-----------------------------------|:-------------------------------------------------|
| Batch Layer   | Apache Spark                       | Processes large-scale historical OHLCV data      |
| Speed Layer   | Kafka + Spark Structured Streaming | Handles real-time data ingestion and analytics   |
| Serving Layer | Flask + Elasticsearch              | Serves aggregated insights and visual dashboards |

---

### Core Technologies

| Category         | Stack                                |
|:-----------------|:-------------------------------------|
| Compute          | Apache Spark 3.5 (batch + streaming) |
| Messaging        | Apache Kafka                         |
| Storage          | S3 / HDFS / Local                    |
| Serving          | Flask, Elasticsearch                 |
| Containerization | Docker, Kubernetes                   |
| CI/CD            | GitHub Actions + GHCR                |
| Cloud            | AWS EKS                              |

---

### How It Works

1. Producer Service (services/producer)
    - Fetches OHLCV (Open–High–Low–Close–Volume) data every minute from Binance.
    - Sends real-time JSON messages to Kafka topic: crypto_ohlcv_1m.

2. Stream Processor (services/stream)
    - Spark Structured Streaming reads Kafka topic.
    - Parses JSON, transforms data, and optionally stores in Elasticsearch or Console.

3. Batch Processor (services/batch)
    - Periodic Spark jobs aggregate historical datasets (hourly/daily).
    - Outputs to S3 or HDFS.

4. Serving Layer (services/web)
    - Flask app reads from Elasticsearch.
    - Provides REST API and dashboard visualization.

---

#### Example Output

```
+----------+----------+----------------------+-------------+--------+
| symbol   | exchange | ts_iso               | close       | volume |
+----------+----------+----------------------+-------------+--------+
| BTC/USDT | binance  | 2025-10-20T14:20:00Z | 94583.21    | 38.92  |
| ETH/USDT | binance  | 2025-10-20T14:20:00Z | 5420.84     | 112.33 |
+----------+----------+----------------------+-------------+--------+
```

---

### Kubernetes Deployment (AWS EKS)

#### Create EKS cluster

```bash
eksctl create cluster \
  --name bigdata-cluster \
  --region ap-southeast-1 \
  --version 1.30 \
  --node-type t3.small \
  --nodes 1 \
  --managed \
  --with-oidc
```

#### Install Spark Operator

```bash
helm repo add spark-operator https://kubeflow.github.io/spark-operator
helm repo update
kubectl create namespace spark-operator
helm install spark spark-operator/spark-operator \
  --namespace spark-operator \
  --set sparkJobNamespace=bigdata \
  --set serviceAccounts.spark.name=spark \
  --set serviceAccounts.spark.create=true
```

#### Deploy Streaming Job

```bash
kubectl apply -f k8s/spark-ohlcv-1m.yaml -n bigdata
kubectl get sparkapplications -n bigdata
```

---

### Monitoring & Logs

Check Spark job status:

```bash
kubectl get sparkapplications -n bigdata
kubectl logs -n bigdata <driver-pod-name> -f
```

Elasticsearch data:

```bash
curl http://localhost:9200/_cat/indices?v
```

---

### Example Dashboard (Flask)

```bash
python services/web/app.py
```

## License

MIT License © 2025 Mysorf