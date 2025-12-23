import logging
from typing import List
from fastapi import APIRouter, FastAPI, HTTPException, Query
from database import es_client # Đảm bảo file database.py của bạn đã kết nối đúng

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_DEBUG")

app = FastAPI()
router = APIRouter()
INDEX_TECHNICAL = "crypto_technical_analysis"

# ============================
# API 1: LATEST PRICES (Cho bảng bên trái)
# ============================
@router.get("/api/latest", response_model=List[dict])
def get_latest_crypto_data(size: int = Query(20)):
    try:
        query = {
            "size": 0,
            "aggs": {
                "symbols": {
                    "terms": {"field": "symbol.keyword", "size": size},
                    "aggs": {
                        "latest": {
                            "top_hits": {
                                "size": 1,
                                "sort": [{"timestamp": {"order": "desc"}}],
                                "_source": {"includes": ["timestamp", "symbol", "close", "rsi_14", "ema_20", "bb_upper"]}
                            }
                        }
                    }
                }
            }
        }

        res = es_client.search(index=INDEX_TECHNICAL, body=query)
        buckets = res.get("aggregations", {}).get("symbols", {}).get("buckets", [])
        
        results = []
        for b in buckets:
            hits = b.get("latest", {}).get("hits", {}).get("hits", [])
            if hits:
                results.append(hits[0]["_source"])
        
        return results

    except Exception as e:
        logger.error(f"Error /latest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# API 2: TECHNICAL CHART (Cho biểu đồ)
# ============================
@router.get("/api/technical", response_model=List[dict])
def get_technical_analysis(
    symbol: str,
    timeframe: str = Query("1m"),
    limit: int = Query(100)
):
    try:
        # Query dữ liệu từ ES (mới -> cũ)
        query = {
            "size": limit,
            "sort": [{"timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"term": {"symbol.keyword": symbol}},
                        {"term": {"timeframe.keyword": timeframe}}
                    ]
                }
            }
        }

        response = es_client.search(index=INDEX_TECHNICAL, body=query)
        hits = response.get("hits", {}).get("hits", [])

        # Lấy nguyên dữ liệu
        raw_data = [hit["_source"] for hit in hits]

        # Đảo mảng (mới -> cũ => cũ -> mới)
        reversed_data = raw_data[::-1]

        # Log kiểm tra
        if reversed_data:
            logger.info(f"[API] {symbol} ({timeframe}): First={reversed_data[0]['timestamp']} -> Last={reversed_data[-1]['timestamp']}")

        return reversed_data

    except Exception as e:
        logger.error(f"Error /technical: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)
