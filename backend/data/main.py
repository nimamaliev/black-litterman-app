from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uvicorn
from . import data_loader
from .engine import BLEngine

app = FastAPI(title="Black-Litterman API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bl_engine = None


@app.on_event("startup")
def startup_event():
    global bl_engine
    print("Loading data...")
    prices = data_loader.load_data()
    bl_engine = BLEngine(prices)
    print("Engine initialized.")


# --- UPDATED DATA MODELS ---
class View(BaseModel):
    ticker: str
    value: float
    confidence: float
    start_date: Optional[str] = None  # NEW: Optional Start Date
    end_date: Optional[str] = None  # NEW: Optional End Date


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
