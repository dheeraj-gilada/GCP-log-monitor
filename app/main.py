from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import os
from app.api import ingestion_routes
from datetime import datetime
import logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "../static")), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../templates"))

# Include API routers
app.include_router(ingestion_routes.router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_dashboard(request: Request):
    return templates.TemplateResponse("monitoring.html", {"request": request})

@app.get("/health")
def health():
    # Simple health check for Redis log storage
    log_storage = ingestion_routes.get_log_ingestion("simulation").log_storage
    try:
        # Try to get current max index as a Redis health check
        import asyncio
        loop = asyncio.get_event_loop()
        max_index = loop.run_until_complete(log_storage.get_current_max_index())
        return JSONResponse({"status": "ok", "redis_max_log_index": max_index})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)})
