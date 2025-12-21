# [FIXED] Use Eclipse Temurin (Official OpenJDK successor) instead of 'openjdk'
FROM eclipse-temurin:8-jdk-jammy

# Install Python 3 and Pip
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for Spark
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the script
COPY batch_ingest.py .

# Command to submit the spark job
CMD ["python3", "batch_ingest.py"]
