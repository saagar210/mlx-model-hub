from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys

# DEBUG: Trace startup
print("DEBUG: Starting main.py imports...", flush=True)

try:
    from app.api.monitor import router as monitor_router
    print("DEBUG: Imported monitor router", flush=True)
    from app.api.preparation import router as preparation_router
    print("DEBUG: Imported preparation router", flush=True)
    from app.api.engine import router as engine_router
    print("DEBUG: Imported engine router", flush=True)

except Exception as e:
    print(f"CRITICAL: Import error: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

app = FastAPI(
    title="Silicon Studio Backend",
    description="Local-first LLM fine-tuning engine",
    version="0.1.0"
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local desktop app compatibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(monitor_router, prefix="/api/monitor", tags=["monitor"])
app.include_router(preparation_router, prefix="/api/preparation", tags=["preparation"])
app.include_router(engine_router, prefix="/api/engine", tags=["engine"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "silicon-studio-engine"}

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    port = int(os.getenv("PORT", 8000))
    # When frozen, we cannot use reload=True and should pass the app object directly
    print(f"DEBUG: Uvicorn starting on port {port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)
