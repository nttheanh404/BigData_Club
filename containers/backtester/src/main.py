from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os

app = FastAPI()

class BacktestRequest(BaseModel):
    rsi_lower: int = 30
    rsi_upper: int = 70

@app.post("/run")
def run_backtest_job(req: BacktestRequest):
    """
    Spawns a Spark Submit process to run the backtest on the cluster.
    """
    print(f"Received request: {req}")
    
    # Configure Command
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    hdfs_path = os.getenv("HDFS_RAW_PATH", "hdfs://hdfs-service:9000/data/crypto/raw_1m")
    
    cmd = [
        "spark-submit",
        "--master", spark_master,
        "--deploy-mode", "client",
        # Important: Ensure the container IP is routable or use Service Name
        "--conf", "spark.driver.host=backtester-service", 
        "--conf", "spark.driver.port=20020",
        "--conf", "spark.blockManager.port=20021",
        "/app/src/backtest_job.py",
        f"--hdfs={hdfs_path}",
        f"--rsi_lower={req.rsi_lower}",
        f"--rsi_upper={req.rsi_upper}"
    ]

    try:
        # Run Spark Job (Blocking call for simplicity, or use BackgroundTasks for async)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse the stdout to find our results table
        # In a real app, the Spark job should write JSON to HDFS/ES, and we read that.
        # For now, we return the raw logs which contain the printed table.
        return {
            "status": "success", 
            "logs": result.stdout
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "status": "error", 
            "error": e.stderr, 
            "logs": e.stdout
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
