#!/bin/bash

NAMESPACE=default

echo "🚀 Starting port-forward..."

# Backend API
kubectl port-forward svc/crypto-backend-svc 8000:8000 -n $NAMESPACE &
echo "✔ crypto-backend -> localhost:8000"

# Frontend (NodePort hoặc service)
kubectl port-forward svc/crypto-frontend-svc 3000:80 -n $NAMESPACE &
echo "✔ crypto-frontend -> localhost:3000"

# Elasticsearch
kubectl port-forward pod/quickstart-es-default-0 9200:9200 -n $NAMESPACE &
echo "✔ Elasticsearch -> localhost:9200"

# Kibana
kubectl port-forward pod/quickstart-kb-fb8d5f67-fd558  5601:5601 -n $NAMESPACE &
echo "✔ Kibana -> localhost:5601"

# HDFS NameNode UI
kubectl port-forward pod/hdfs-namenode-0 9870:9870 -n $NAMESPACE &
echo "✔ HDFS NameNode UI -> localhost:9870"

wait
