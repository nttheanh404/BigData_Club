# Use a stable Python version
FROM python:3.11-slim-bookworm

# ==========================================
# 1. INSTALL SYSTEM DEPENDENCIES
# ==========================================
# Cài thêm 'wget' phòng hờ cần tải jar thủ công
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    default-jre-headless \
    procps \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# 2. CONFIGURE ENVIRONMENT VARIABLES
# ==========================================
ENV JAVA_HOME="/usr/lib/jvm/default-java"
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3

WORKDIR /opt/app

# ==========================================
# 3. INSTALL PYTHON LIBRARIES
# ==========================================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# 4. SETUP APPLICATION & MODELS
# ==========================================
# Tạo thư mục chờ sẵn để mount volume
RUN mkdir -p /opt/models /mnt/truststore

# Copy code (Đảm bảo tên file khớp với tên bạn đang code)
COPY stream_processor.py spark_streaming.py
COPY models/xgb_model.pkl /opt/models/xgb_model.pkl
COPY models/scaler.pkl /opt/models/scaler.pkl

# ==========================================
# 5. DEPENDENCY WARMUP
# ==========================================
# Tự động tải thư viện Kafka và ES về cache image
# Lưu ý: Phiên bản ở đây phải khớp với phiên bản Spark bạn cài trong requirements.txt
# Ví dụ: Nếu pip install pyspark==3.5.0 thì dùng gói spark-sql-kafka...3.5.0
RUN echo "from pyspark.sql import SparkSession; spark = SparkSession.builder.master('local').getOrCreate(); print('Warmup OK')" > /tmp/warmup.py && \
    spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.elasticsearch:elasticsearch-spark-30_2.12:8.11.1 \
    /tmp/warmup.py && \
    rm /tmp/warmup.py

# ==========================================
# 6. EXECUTION COMMAND
# ==========================================
# Chỉ cần gọi spark-submit với các packages.
# Các cấu hình SSL đã được xử lý trong code Python.
CMD ["spark-submit", \
     "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.elasticsearch:elasticsearch-spark-30_2.12:8.11.1", \
     "spark_streaming.py"]
