"""
Main FastAPI application for GCP Log Monitoring system.
Entry point with middleware, WebSocket, and route configuration.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

from app.config import settings
from app.api.routes import router as api_router
from app.api.websockets import websocket_router


# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered GCP log monitoring with anomaly detection",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(websocket_router, prefix="/ws")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard."""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "title": settings.app_name}
    )


@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring(request: Request):
    """Serve the monitoring dashboard."""
    return templates.TemplateResponse(
        "monitoring.html", 
        {"request": request, "title": f"{settings.app_name} - Live Monitoring"}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug
    }


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    
    # TODO: Initialize monitoring engine
    # TODO: Validate configurations
    # TODO: Setup background tasks
    
    if settings.debug:
        print("📊 Debug mode enabled")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("🛑 Shutting down GCP Log Monitoring system")
    
    # TODO: Cleanup monitoring engine
    # TODO: Close connections


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )
