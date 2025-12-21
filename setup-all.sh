#!/bin/bash

# --- CẤU HÌNH MÀU SẮC LOG ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# --- BIẾN CẤU HÌNH ---
DEPLOY_FILE="./deploy/full-stack-deploy.yaml"
KIND_CONFIG="kind-multinode.yaml"
CLUSTER_NAME="kind"

echo -e "${GREEN}██████╗ ██╗ ██████╗      ██████╗  █████╗ ████████╗${NC}"
echo -e "${GREEN}██╔══██╗██║██╔════╝      ██╔══██╗██╔══██╗╚══██╔══╝${NC}"
echo -e "${GREEN}██████╔╝██║██║  ███╗     ██║  ██║███████║   ██║   ${NC}"
echo -e "${GREEN}██╔══██╗██║██║   ██║     ██║  ██║██╔══██║   ██║   ${NC}"
echo -e "${GREEN}██████╔╝██║╚██████╔╝     ██████╔╝██║  ██║   ██║   ${NC}"
echo -e "${GREEN}╚═════╝ ╚═╝ ╚═════╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ${NC}"
echo -e "${BLUE}>>> AUTOMATED SETUP SCRIPT FOR KUBERNETES BIG DATA STACK <<<${NC}"
echo ""

# 1. KIỂM TRA FILE
if [ ! -f "$DEPLOY_FILE" ]; then
    echo -e "${RED}[LỖI] Không tìm thấy file $DEPLOY_FILE${NC}"
    exit 1
fi
if [ ! -f "$KIND_CONFIG" ]; then
    echo -e "${RED}[LỖI] Không tìm thấy file $KIND_CONFIG${NC}"
    exit 1
fi

# 2. DỌN DẸP
echo -e "${YELLOW}[1/7] Dọn dẹp môi trường cũ...${NC}"
kind delete cluster --name $CLUSTER_NAME
rm -f elastic-truststore.jks ca.crt # Xóa file temp cũ
echo "Đang xóa dữ liệu cũ trong ./data ..."
sudo rm -rf ./data

# 3. CHUẨN BỊ DATA
echo -e "${YELLOW}[2/7] Tạo thư mục data local...${NC}"
mkdir -p ./data/kafka ./data/es ./data/hdfs
sudo chmod -R 777 ./data
echo "✅ Đã tạo ./data (Kafka, ES, HDFS)"

# 4. TẠO CLUSTER
echo -e "${YELLOW}[3/7] Khởi tạo Cluster Kind (Multi-node)...${NC}"
kind create cluster --config $KIND_CONFIG --name $CLUSTER_NAME

echo "⏳ Đợi 10s cho nodes sẵn sàng..."
sleep 10

# 5. DEPLOY BASE (Namespace & Resources)
echo -e "${YELLOW}[4/7] Deploy toàn bộ hệ thống (Lần 1)...${NC}"
# Lưu ý: Các pod dùng JKS sẽ crash loop lúc này, ta sẽ fix ở bước sau
kubectl apply -f $DEPLOY_FILE

# 6. XỬ LÝ SSL/TLS (TỰ ĐỘNG TẠO JKS TỪ ELASTICSEARCH)
echo -e "${YELLOW}[5/7] Đợi Elasticsearch tạo Certificates...${NC}"
echo "⏳ Đang chờ secret 'quickstart-es-http-certs-public' xuất hiện..."

# Loop chờ cho đến khi secret được tạo bởi ECK Operator
while ! kubectl get secret quickstart-es-http-certs-public > /dev/null 2>&1; do
  sleep 5
  echo -n "."
done
echo -e "\n✅ Secret đã xuất hiện!"

echo -e "${BLUE}>>> Đang trích xuất CA Cert và tạo Java Keystore (JKS)...${NC}"
# Lấy CA Certificate
kubectl get secret quickstart-es-http-certs-public -o jsonpath='{.data.ca\.crt}' | base64 -d > ca.crt

# Sử dụng Docker để chạy keytool (không cần cài Java trên máy host)
# Nếu bạn có Java cài sẵn, có thể thay thế bằng lệnh keytool trực tiếp
if docker --version > /dev/null 2>&1; then
    echo "Using Docker to generate JKS..."
    docker run --rm -v $(pwd):/work -w /work eclipse-temurin:17-jdk \
    keytool -import -trustcacerts -noprompt -alias elastic -file ca.crt -keystore elastic-truststore.jks -storepass changeit
else
    # Fallback nếu máy host có java
    echo "Docker not found, trying local keytool..."
    keytool -import -trustcacerts -noprompt -alias elastic -file ca.crt -keystore elastic-truststore.jks -storepass changeit
fi

if [ -f "elastic-truststore.jks" ]; then
    echo -e "${GREEN}✅ File JKS đã được tạo thành công!${NC}"
    
    # Tạo secret es-truststore
    echo "Đang tạo Kubernetes Secret 'es-truststore'..."
    kubectl delete secret es-truststore --ignore-not-found
    kubectl create secret generic es-truststore --from-file=elastic-truststore.jks

    # Restart các pod bị lỗi để nhận secret mới
    echo "🔄 Restarting Spark & Backtest pods để nhận chứng chỉ mới..."
    kubectl rollout restart deployment crypto-stream-processor
    kubectl rollout restart deployment backtest-api
else
    echo -e "${RED}[LỖI] Không thể tạo file JKS. Kiểm tra lại Docker hoặc Java.${NC}"
fi

# 7. PORT FORWARDING
echo -e "${YELLOW}[6/7] Thiết lập truy cập...${NC}"

# Kill process port-forward cũ nếu còn chạy
pkill -f "port-forward service/crypto-frontend-svc" || true

echo -e "${BLUE}Các dịch vụ đã được map qua Kind Config (Truy cập trực tiếp):${NC}"
echo "   - Kafka External: localhost:9092"
echo "   - Elasticsearch:  https://localhost:9200 (User: elastic)"
echo "   - HDFS UI:        http://localhost:9870"

echo -e "${BLUE}Đang thiết lập Port-Forward cho Frontend (Chạy ngầm)...${NC}"
# Chạy port-forward ẩn
nohup kubectl port-forward service/crypto-frontend-svc 30080:80 > /dev/null 2>&1 &

echo -e "${GREEN}✅ Setup hoàn tất!${NC}"
echo "--------------------------------------------------------"
echo "👉 Frontend App:    http://localhost:30080"
echo "👉 Lấy pass Elastic: kubectl get secret quickstart-es-elastic-user -o go-template='{{.data.elastic | base64decode}}'"
echo "--------------------------------------------------------"
echo "Kiểm tra trạng thái pod: kubectl get pods -A"
