from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.admin_api.routers import batches, complexes, data_explorer, jobs, runs, settings
from src.core.logging import logger

# Create FastAPI app
app = FastAPI(
    title="KB Estate Collector Admin API",
    description="관리자 API for KB 부동산 데이터 수집 시스템",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(complexes.router, prefix="/api/complexes", tags=["Complexes"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(runs.router, prefix="/api/runs", tags=["Runs"])
app.include_router(data_explorer.router, prefix="/api/data", tags=["Data"])
app.include_router(batches.router, prefix="/api/batches", tags=["Batches"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "KB Estate Collector",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    logger.info("Starting KB Estate Collector Admin API")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down KB Estate Collector Admin API")
