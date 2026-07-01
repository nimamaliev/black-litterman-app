import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uvicorn
# --- FIXED IMPORTS ---
from app import data_loader       # Changed from . import data_loader
from app.engine import BLEngine   # Changed from .engine import BLEngine
# ---------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bl_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Modern FastAPI startup/shutdown handling (replaces deprecated on_event).
    global bl_engine
    logger.info("Loading data...")
    prices = data_loader.load_data()
    bl_engine = BLEngine(prices)
    logger.info("Engine initialized.")
    yield
    # (no shutdown work required)


app = FastAPI(title="Black-Litterman API", lifespan=lifespan)

# --- CORS ---
# This API uses no cookies/auth, so credentials are disabled. A wildcard origin
# is only valid when credentials are off. Restrict origins in production by
# setting ALLOWED_ORIGINS (comma-separated) in the environment.
_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- UPDATED DATA MODELS ---
class View(BaseModel):
    ticker: str
    value: float
    confidence: float
    start_date: Optional[str] = None  # Optional Start Date (applied in backtest)
    end_date: Optional[str] = None  # Optional End Date (applied in backtest)


class ScenarioRequest(BaseModel):
    views: List[View]
    date: Optional[str] = None


class MonteCarloRequest(BaseModel):
    mu: float
    sigma: float
    days: int = 252


class RecommendationResponse(BaseModel):
    date: str
    weights: Dict[str, float]
    regime: Dict[str, Any]
    metrics: Dict[str, float]


class BacktestRequest(BaseModel):
    start_date: str
    end_date: str
    views: List[View]


# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"status": "System Operational", "model": "Black-Litterman ML"}


@app.post("/recommendation/scenario")
def run_scenario(request: ScenarioRequest):
    if not bl_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")

    # Dashboard scenario usually ignores dates (applies "Now"), but passing just in case
    result = bl_engine.run_scenario([v.dict() for v in request.views], target_date=request.date)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/simulation/monte_carlo")
def run_monte_carlo(request: MonteCarloRequest):
    if not bl_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    return bl_engine.run_monte_carlo(request.mu, request.sigma, request.days)


@app.post("/simulation/backtest")
def run_backtest(request: BacktestRequest):
    if not bl_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")

    # Pass the full view dictionary (including dates) to the engine
    result = bl_engine.run_backtest(
        request.start_date,
        request.end_date,
        [v.dict() for v in request.views]
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


if __name__ == "__main__":

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
