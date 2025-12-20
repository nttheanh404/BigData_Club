from fastapi import FastAPI
from es_route import router as es_router

app = FastAPI()

# Register the route
app.include_router(es_router, prefix="/api") # Adjust prefix as needed

@app.get("/")
def health_check():
    return {"status": "running"}
