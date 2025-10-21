# Big Data Crypto

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

### Project Structure

```
Bigdata/
│
├── services/
│   ├── producer/         # Kafka producers (collect OHLCV data)
│   ├── stream/           # Spark streaming (real-time analytics)
│   ├── batch/            # Batch layer (Spark historical jobs)
│   ├── web/              # Flask dashboard + API gateway
│   └── utils/            # Shared helpers (API, HDFS, Elastic,...)
│
├── docker/               # Dockerfile for each service
├── k8s/                  # Kubernetes manifests
├── scripts/              # Utility scripts (run, deploy, cron)
│
├── data/                 # Sample data for local test
├── logs/                 # Runtime logs
│
├── .env.example          # Example environment configuration
├── requirements.txt      # Python dependencies
├── .gitignore
└── README.md
```

---