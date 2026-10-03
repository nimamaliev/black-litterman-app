"""Live track record: an append-only log of what the model actually recommended.

Each row is written once, on the day it is produced, by
backend/record_recommendation.py (run daily by the GitHub Actions workflow
.github/workflows/track-record.yml, which commits the CSV to the `track-record`
branch, so git history timestamps every row and nothing can be back-filled
quietly).

Performance is then measured going forward only: the recommendation made with
data through day d is assumed to be traded at the close of day d and held until
the next recommendation.
"""
import io
import logging
import os
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from app.engine import MODEL_VERSION, COST_PER_TRADE, perf_metrics

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACK_FILE = os.path.join(BASE_DIR, "track_record", "recommendations.csv")
DEFAULT_URL = ("https://raw.githubusercontent.com/nimamaliev/black-litterman-app/"
               "track-record/backend/track_record/recommendations.csv")


def build_row(engine) -> dict:
    """Today's live recommendation (no user views) as a flat CSV row."""
    rec = engine.run_scenario([])
    if "error" in rec:
        raise RuntimeError(rec["error"])
    row = {
        "data_date": rec["date"],
        "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": rec.get("model_version", MODEL_VERSION),
        "invested": round(rec["exposure"]["invested"], 6),
    }
    for t in engine.tickers:
        row[f"w_{t}"] = round(rec["weights"].get(t, 0.0), 6)
    return row


def append_row(row: dict, path: str = TRACK_FILE) -> bool:
    """Append `row` unless a row for the same data date already exists.

    Returns True if a row was written."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        existing = pd.read_csv(path, dtype={"data_date": str})
        if row["data_date"] in set(existing["data_date"]):
            return False
        out = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    else:
        out = pd.DataFrame([row])
    out.to_csv(path, index=False)
    return True


def load_records(path: str = TRACK_FILE, url: str = None) -> pd.DataFrame:
    """Records from TRACK_RECORD_URL / the public branch, else the local file."""
    url = url if url is not None else os.environ.get("TRACK_RECORD_URL", DEFAULT_URL)
    if url:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                text = resp.read().decode("utf-8")
            if text.strip():
                return pd.read_csv(io.StringIO(text), dtype={"data_date": str})
        except Exception as e:
            logger.warning("Could not fetch track record from %s (%s)", url, e)
    if os.path.exists(path):
        return pd.read_csv(path, dtype={"data_date": str})
    return pd.DataFrame()


def evaluate(records: pd.DataFrame, engine, initial_capital: float = 10000.0) -> dict:
    """Forward performance of the recorded recommendations vs SPY."""
    if records is None or records.empty:
        return {"records": [], "message": "No live recommendations have been recorded yet."}

    records = records.sort_values("data_date").drop_duplicates("data_date", keep="first")
    px = engine.asset_prices[engine.tickers]
    idx = px.index
    rec_rows = []
    for _, r in records.iterrows():
        d = pd.Timestamp(r["data_date"])
        w = pd.Series({t: float(r.get(f"w_{t}", 0.0) or 0.0) for t in engine.tickers})
        rec_rows.append((d, w, float(r.get("invested", 1.0))))

    asset_rets = px.pct_change()
    rf = engine.rf_daily
    out, held, held_exp = [], None, 0.0
    for k, (d, w, inv) in enumerate(rec_rows):
        nxt = rec_rows[k + 1][0] if k + 1 < len(rec_rows) else idx[-1] + pd.Timedelta(days=1)
        days = idx[(idx > d) & (idx <= nxt)] if k + 1 < len(rec_rows) else idx[idx > d]
        if len(days) == 0:
            continue
        target = w * inv
        prev = held * held_exp if held is not None else pd.Series(0.0, index=w.index)
        cost = float((target - prev).abs().sum()) * COST_PER_TRADE
        cur = w.copy()
        for n, day in enumerate(days):
            r_assets = asset_rets.loc[day].fillna(0.0)
            r = inv * float((cur * r_assets).sum()) + (1 - inv) * float(rf.get(day, 0.0))
            if n == 0:
                r -= cost
            out.append((day, r))
            grown = cur * (1 + r_assets)
            cur = grown / grown.sum() if grown.sum() > 0 else cur
        held, held_exp = cur, inv

    payload = {
        "records": [{"data_date": str(d.date()), "invested": inv,
                     "weights": {t: float(v) for t, v in w.items()}} for d, w, inv in rec_rows],
        "first_record": str(rec_rows[0][0].date()),
        "last_record": str(rec_rows[-1][0].date()),
    }
    if not out:
        payload["message"] = "Recommendations recorded, but no trading days have passed since the first one."
        return payload

    rets = pd.Series(dict(out)).sort_index()
    spy = engine.market_prices.pct_change().reindex(rets.index).fillna(0.0)
    payload.update({
        "dates": [str(d.date()) for d in rets.index],
        "portfolio": ((1 + rets).cumprod() * initial_capital).tolist(),
        "spy": ((1 + spy).cumprod() * initial_capital).tolist(),
        "metrics": perf_metrics(rets, rf),
        "spy_metrics": perf_metrics(spy, rf),
        "trading_days": int(len(rets)),
    })
    if len(rets) < 252:
        payload["message"] = (f"Only {len(rets)} trading days of live history so far; "
                              "metrics are not yet meaningful.")
    return payload
