import os
import logging
import ssl  # <--- Import SSL module
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

# Read Environment Variables
ES_HOST = os.getenv("ES_HOST", "https://quickstart-es-http.default.svc.cluster.local:9200")
ES_PASSWORD = os.getenv("ELASTIC_PASSWORD", "changeme")
ES_CA_CERT = os.getenv("ES_CA_CERT_PATH", "/mnt/certs/ca.crt")
ES_USER = "elastic"

def get_es_client():
    """Singleton ES Client Factory"""
    try:
        if not os.path.exists(ES_CA_CERT):
            logger.warning(f"⚠️ CA Cert not found at {ES_CA_CERT}")

        # --- FIX START: Create custom SSL Context ---
        # This tells Python: "Trust the CA file, but don't strictly check the domain name."
        context = ssl.create_default_context(cafile=ES_CA_CERT)
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_REQUIRED
        # --- FIX END ---

        client = Elasticsearch(
            ES_HOST,
            basic_auth=(ES_USER, ES_PASSWORD),
            ssl_context=context  # <--- Pass the custom context here
        )
        return client
    except Exception as e:
        logger.error(f"❌ Failed to init ES client: {e}")
        raise e

es_client = get_es_client()
