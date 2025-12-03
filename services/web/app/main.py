import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from services.web.app.routes import es_routes

app = FastAPI(title="Crypto Prediction Dashboard", version="1.0.0")

# --- Middleware ---
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# --- Include API routes ---
app.include_router(es_routes.router, prefix="/api", tags=["elasticsearch"])

# --- Serve frontend (static) ---
frontend_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")


@app.get("/health")
def health():
  return {"ok": True, "service": "web-dashboard"}


if __name__ == "__main__":
  import uvicorn

  port = int(os.getenv("PORT", "8000"))
  uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)