from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import subprocess
import os
import socket
import hashlib
from datetime import datetime
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class BacktestRequest(BaseModel):
    rsi_low: int = 30
    rsi_high: int = 70

def generate_job_id(rsi_low: int, rsi_high: int) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    raw = f"{rsi_low}-{rsi_high}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"bt_{ts}_{h}"

def run_spark_command(cmd):
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        logger.error(f"Spark Job Failed: {e}")

@app.post("/run-backtest")
async def trigger_backtest(req: BacktestRequest, background_tasks: BackgroundTasks):
    job_id = generate_job_id(req.rsi_low, req.rsi_high)

    pod_ip = os.getenv("POD_IP", socket.gethostbyname(socket.gethostname()))
    hdfs_path = os.getenv("HDFS_RAW_PATH")
    image_name = os.getenv("CONTAINER_IMAGE")
    cmd = [
    "/opt/spark/bin/spark-submit",
    "--master", "k8s://https://kubernetes.default.svc:443",
    "--deploy-mode", "client",

    "--packages",
    "org.elasticsearch:elasticsearch-spark-30_2.12:8.11.0",

    # ===== IMAGE =====
    "--conf", f"spark.kubernetes.container.image={image_name}",
     
    "--conf", "spark.executor.instances=1",
    "--conf", "spark.executor.cores=1",
    "--conf", "spark.dynamicAllocation.enabled=false",



    # ===== MOUNT SECRET (CÁCH ĐÚNG) =====
    "--conf", "spark.kubernetes.executor.secrets.es-truststore=/mnt/truststore",
    "--conf", "spark.kubernetes.driver.secrets.es-truststore=/mnt/truststore",

    # ===== NETWORK / MEMORY =====
    "--conf", f"spark.driver.host={pod_ip}",
    "--conf", "spark.driver.bindAddress=0.0.0.0",
    "--conf", "spark.driver.port=39393",
    "--conf", "spark.blockManager.port=38883",
    "--conf", "spark.executor.memory=512m",
    "--conf", "spark.driver.memory=512m",
    "--conf", "spark.kubernetes.executor.request.cores=0.5",
    "--conf", "spark.kubernetes.authenticate.driver.serviceAccountName=spark-sa",

    "backtest_job.py",
    "--hdfs_path", hdfs_path,
    "--rsi_low", str(req.rsi_low),
    "--rsi_high", str(req.rsi_high),
    "--job_id", job_id
]

    background_tasks.add_task(run_spark_command, cmd)

    return {
        "status": "submitted",
        "job_id": job_id,
        "params": req
    }

@app.get("/get-results/{job_id}")
async def get_results(job_id: str):
    es_url = "http://quickstart-es-http:9200/backtest_results/_search"
    query = {"query": {"term": {"job_id": job_id}}}

    try:
        resp = requests.get(es_url, json=query).json()
        hits = resp.get("hits", {}).get("hits", [])
        return {
            "job_id": job_id,
            "results": [h["_source"] for h in hits]
        }
    except Exception as e:
        return {"error": str(e)}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
