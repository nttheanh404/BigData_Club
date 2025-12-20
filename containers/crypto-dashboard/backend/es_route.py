from fastapi import APIRouter, HTTPException
from database import es_client
import logging

# Initialize router and logger
router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/latest")
def get_latest_crypto_data(size: int = 10):
    """
    Fetches the latest data for unique crypto symbols from the PREDICTION index.
    Returns a clean list of objects, e.g., [{ "symbol": "BTC", "price": 50000 }, ...]
    """
    try:
        # 1. Define the Aggregation Query
        query = {
            "size": 0,  # We don't want raw hits, only aggregations
            "aggs": {
                "symbols": {
                    "terms": {"field": "symbol.keyword", "size": size},
                    "aggs": {
                        "latest": {
                            "top_hits": {
                                "size": 1,
                                "sort": [{"@timestamp": {"order": "desc"}}],
                                "_source": {
                                    "includes": [
                                        "@timestamp", 
                                        "symbol", 
                                        "close", 
                                        "volume", 
                                        "rsi", 
                                        "ema_20", 
                                        "predicted_price"
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        }

        # 2. Execute the Search
        response = es_client.search(index="crypto_prediction_1m", body=query)

        # 3. Parse the Response
        clean_data = []
        buckets = response.get("aggregations", {}).get("symbols", {}).get("buckets", [])

        for bucket in buckets:
            hits = bucket.get("latest", {}).get("hits", {}).get("hits", [])
            if hits:
                source_data = hits[0]["_source"]
                clean_data.append(source_data)

        return clean_data

    except Exception as e:
        logger.error(f"Error in /latest endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_crypto_history(symbol: str, minutes: int = 60):
    """
    Fetch historical data for a specific symbol over the last X minutes from PREDICTION index.
    Example: /history?symbol=BTC/USDT&minutes=60
    """
    try:
        query = {
            "size": 1000, 
            "sort": [{"@timestamp": {"order": "asc"}}], 
            "query": {
                "bool": {
                    "must": [
                        {"term": {"symbol.keyword": symbol}},
                        {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}}
                    ]
                }
            },
            "_source": ["@timestamp", "close", "predicted_price", "symbol"] 
        }

        response = es_client.search(index="crypto_prediction_1m", body=query)
        hits = response.get("hits", {}).get("hits", [])
        clean_data = [hit["_source"] for hit in hits]

        return clean_data

    except Exception as e:
        logger.error(f"Error in /history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
#  NEW ENDPOINT: TECHNICAL ANALYSIS
# ==========================================
@router.get("/technical")
def get_technical_analysis(symbol: str, timeframe: str = "1m", limit: int = 100):
    """
    Fetch ALL fields (prices + indicators) from the 'crypto_technical_analysis' index.
    """
    try:
        query = {
            "size": limit,
            "sort": [{"@timestamp": {"order": "desc"}}], # Get newest first
            "query": {
                "bool": {
                    "must": [
                        {"term": {"symbol.keyword": symbol}},
                        {"term": {"timeframe.keyword": timeframe}}
                    ]
                }
            }
            # REMOVED: "_source": [...] 
            # Removing this key tells Elasticsearch to return the full document.
        }

        # Query the index
        response = es_client.search(index="crypto_technical_analysis", body=query)
        
        hits = response.get("hits", {}).get("hits", [])
        
        # Reverse the list so it's [Oldest -> Newest] for frontend charts
        clean_data = [hit["_source"] for hit in hits][::-1]

        return clean_data

    except Exception as e:
        logger.error(f"Error in /technical: {e}")
        raise HTTPException(status_code=500, detail=str(e))
