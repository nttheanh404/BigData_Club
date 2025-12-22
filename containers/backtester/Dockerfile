FROM apache/spark:3.5.0-python3
USER root
WORKDIR /opt/app

# Cài đầy đủ các thư viện cần thiết
RUN pip3 install --no-cache-dir \
    pandas \
    pyarrow \
    numpy \
    fastapi \
    uvicorn \
    pydantic \
    requests

# Phân quyền cho Ivy (để tải package Spark-ES) và app folder
RUN mkdir -p /home/spark/.ivy2/cache && \
    chown -R 185:0 /home/spark && \
    chmod -R 775 /home/spark && \
    chown -R 185:0 /opt/app

# Copy toàn bộ code vào
COPY main.py .
COPY backtest_job.py .

USER 185
EXPOSE 8000
CMD ["python3", "main.py"]
