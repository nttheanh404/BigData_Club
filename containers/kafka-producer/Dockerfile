# Base image Python nhẹ
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy code và requirements
COPY producer.py /app/producer.py
COPY requirements.txt /app/requirements.txt

# Cài đặt Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy file .env nếu có
COPY .env /app/.env

# Cho Python in log realtime
ENV PYTHONUNBUFFERED=1

# Chạy producer khi container start
CMD ["python", "producer.py"]
