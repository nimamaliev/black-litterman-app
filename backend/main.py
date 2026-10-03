import os
import json
import logging
import threading
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uvicorn
# --- FIXED IMPORTS ---
from app import data_loader       # Changed from . import data_loader
from app.engine import BLEngine   # Changed from .engine import BLEngine
from app.growth_engine import GrowthEngine
from app import track_record
# ---------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bl_engine = None
growth_engine = None

# Backtests are deterministic for a given (dates, views) on a given engine, so
# repeat requests are served from memory. Cleared whenever the engine is rebuilt.
_BACKTEST_CACHE_MAX = 64
_backtest_cache: "OrderedDict[str, dict]" = OrderedDict()
_backtest_lock = threading.Lock()


def _refresh_engine_in_background():
    """Download any missing recent prices and swap in a fresh engine.

    Startup serves the cached prices immediately; this runs afterwards so a
    cold start is not blocked on Yahoo Finance.
    """
    global bl_engine, growth_engine
    try:
        if data_loader.refresh_if_stale():
            fresh_prices = data_loader.read_prices()
            new_engine = BLEngine(fresh_prices)
            _warm_engine(new_engine)
            new_growth = GrowthEngine(fresh_prices)
            bl_engine = new_engine  # atomic reference swaps
            growth_engine = new_growth
            with _backtest_lock:
                _backtest_cache.clear()
            logger.info("Background refresh complete; engine updated.")
    except Exception:
        logger.exception("Background data refresh failed; continuing with cached data.")


def _warm_engine(engine):
    try:
        engine.run_scenario([])
    except Exception:
        logger.exception("Engine warm-up failed; it will build lazily instead.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Modern FastAPI startup/shutdown handling (replaces deprecated on_event).
    global bl_engine, growth_engine
    logger.info("Loading cached data...")
    prices = data_loader.read_prices()
    if prices.empty:
        # No cache at all: we have no choice but to download before serving.
        prices = data_loader.load_data()
        bl_engine = BLEngine(prices)
        growth_engine = GrowthEngine(prices)
    else:
        bl_engine = BLEngine(prices)
        growth_engine = GrowthEngine(prices)
        threading.Thread(target=_refresh_engine_in_background, daemon=True).start()
    # Build the ML training set now so the first dashboard request is fast.
    threading.Thread(target=_warm_engine, args=(bl_engine,), daemon=True).start()
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
    versus: Optional[str] = None  # relative view: `ticker` beats `versus` by `value`
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
    overlay: bool = True  # apply the volatility-targeting overlay


# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"status": "System Operational", "model": "Black-Litterman"}


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

    engine = bl_engine
    views = [v.dict() for v in request.views]
    key = json.dumps([request.start_date, request.end_date, views, request.overlay], sort_keys=True)

    with _backtest_lock:
        cached = _backtest_cache.get(key)
        if cached is not None:
            _backtest_cache.move_to_end(key)
            return cached

    # Pass the full view dictionary (including dates) to the engine
    result = engine.run_backtest(request.start_date, request.end_date, views, overlay=request.overlay)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Only cache if the engine wasn't swapped while we were computing.
    with _backtest_lock:
        if engine is bl_engine:
            _backtest_cache[key] = result
            while len(_backtest_cache) > _BACKTEST_CACHE_MAX:
                _backtest_cache.popitem(last=False)

    return result


# --- LIVE TRACK RECORD ---
_TRACK_TTL_SECONDS = 3600
_track_cache: Dict[str, Any] = {"at": 0.0, "engine": None, "value": None}


@app.get("/track_record")
def get_track_record():
    """Forward performance of the recommendations recorded daily by the
    track-record workflow (append-only, committed to the `track-record` branch)."""
    if not bl_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    engine = bl_engine
    now = time.time()
    if (_track_cache["value"] is not None and _track_cache["engine"] is engine
            and now - _track_cache["at"] < _TRACK_TTL_SECONDS):
        return _track_cache["value"]
    result = track_record.evaluate(track_record.load_records(), engine)
    _track_cache.update({"at": now, "engine": engine, "value": result})
    return result


# --- GROWTH STRATEGY (volatility-managed SPY) ---
class GrowthScenarioRequest(BaseModel):
    date: Optional[str] = None
    target_vol: float = 0.20
    max_leverage: float = 1.5


class GrowthBacktestRequest(BaseModel):
    start_date: str
    end_date: str
    target_vol: float = 0.20
    max_leverage: float = 1.5


@app.post("/growth/scenario")
def run_growth_scenario(request: GrowthScenarioRequest):
    if not growth_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    result = growth_engine.run_scenario(request.date, request.target_vol, request.max_leverage)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/growth/backtest")
def run_growth_backtest(request: GrowthBacktestRequest):
    if not growth_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")

    engine = growth_engine
    key = "growth:" + json.dumps(
        [request.start_date, request.end_date, request.target_vol, request.max_leverage]
    )
    with _backtest_lock:
        cached = _backtest_cache.get(key)
        if cached is not None:
            _backtest_cache.move_to_end(key)
            return cached

    result = engine.run_backtest(
        request.start_date, request.end_date, request.target_vol, request.max_leverage
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    with _backtest_lock:
        if engine is growth_engine:
            _backtest_cache[key] = result
            while len(_backtest_cache) > _BACKTEST_CACHE_MAX:
                _backtest_cache.popitem(last=False)
    return result


if __name__ == "__main__":

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
