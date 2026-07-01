"""parameter_sweep.py

One-at-a-time (OAT) sensitivity tests for the Black-Litterman strategy.

IMPORTANT: This file does NOT modify the engine or any app code. It imports the
engine, then *temporarily* overrides ONE configuration constant at a time,
re-runs the full-history backtest, records the result, and restores the
original value. Nothing on disk is changed.

Run it from the backend/ folder:

    cd backend
    python parameter_sweep.py

For each parameter it prints a small table comparing several candidate values
against the current baseline, on the metrics that matter for this model:
  CAGR (annual growth), Sharpe & Sortino (risk-adjusted), Max drawdown (crash
  resilience), Last-3-year return (the model's current weak spot), and the
  share of years that beat SPY.

It also writes sweep_results.csv with every run so you can sort and compare.

NOTE ON RUNTIME: a full run does ~15 separate 19-year backtests and can take a
few minutes. For quick iteration, set FAST_START to a later date (e.g.
\"2015-01-01\"); set it back to None for the final, full-history numbers.

NOTE ON THE WEIGHT CAP: the single-sector cap (0.30 / 0.40) is hard-coded inside
engine.run_backtest, so it is the one knob this external harness cannot override
without a small edit to engine.py. Every parameter in SWEEPS below IS overridable
externally.
"""

import sys
import numpy as np
import pandas as pd

from app import data_loader
import app.engine as eng
from app.engine import BLEngine

# Set to a date string like "2015-01-01" for faster (shorter) runs, or None to
# use the full available history.
FAST_START = None

# Each entry maps a constant name -> candidate values to try. The current
# baseline value is detected automatically and always shown for comparison.
SWEEPS = {
    "TURNOVER_SKIP_THRESHOLD": [0.04, 0.08, 0.12],
    "VIEW_Z_CUTOFF_BASE": [0.25, 0.35, 0.45],
    "REBALANCE_FREQ": [21, 63, 126],
    "TRAIN_WINDOW": [378, 504, 756],
    "DELTA_SMOOTH": [0.5, 0.7, 0.9],
    "COST_PER_TRADE": [0.0, 0.0005, 0.0015],
    "CONC_MOM_BONUS": [0.0, 0.20, 0.40],
    # Sector weight caps (now wired to the engine's MAX_WEIGHT / CONC_MAX_WEIGHT
    # constants). Raising these lets the model ride concentrated leaders harder,
    # which directly targets the recent-bull lag.
    "MAX_WEIGHT": [0.30, 0.35, 0.40],
    "CONC_MAX_WEIGHT": [0.40, 0.50, 0.60],
}


def _metrics_from_backtest(res):
    dates = pd.to_datetime(pd.Index(res["dates"]))
    port = pd.Series(res["portfolio"], index=dates, dtype=float)
    rf = res["metrics"].get("risk_free", 0.0)

    rets = port.pct_change().dropna()
    years = (port.index[-1] - port.index[0]).days / 365.25
    cagr = (port.iloc[-1] / port.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    vol = rets.std() * np.sqrt(252)
    sharpe = (rets.mean() * 252 - rf) / vol if vol > 0 else 0.0
    dn = rets[rets < 0].std() * np.sqrt(252)
    sortino = (rets.mean() * 252 - rf) / dn if dn and dn > 0 else 0.0
    max_dd = float((port / port.cummax() - 1).min())

    cutoff = port.index[-1] - pd.Timedelta(days=365 * 3)
    p3 = port.loc[port.index >= cutoff]
    last3 = p3.iloc[-1] / p3.iloc[0] - 1 if len(p3) > 1 else np.nan

    yt = res.get("yearly_table", [])
    wins = sum(1 for r in yt if r["diff"] > 0)
    winrate = wins / len(yt) if yt else np.nan

    return {
        "cagr": cagr, "sharpe": sharpe, "sortino": sortino, "max_dd": max_dd,
        "last3yr": last3, "winrate": winrate,
        "total_return": res["metrics"]["total_return"],
    }


def run_once(engine, start, end, overrides):
    """Apply {const: value} overrides, run a backtest, then restore.

    Any failure in a single variant (e.g. the pypfopt solver reporting an
    infeasible problem at one rebalance date) is caught and reported as a
    skipped run, so one bad variant never aborts the whole sweep. The original
    constant values are always restored, even on failure.
    """
    saved = {k: getattr(eng, k) for k in overrides}
    try:
        for k, v in overrides.items():
            setattr(eng, k, v)
        res = engine.run_backtest(start, end, [])
    except Exception as e:
        print(f"    -> run failed, skipping: {type(e).__name__}: {e}", flush=True)
        return None
    finally:
        for k, v in saved.items():
            setattr(eng, k, v)
    if "error" in res:
        return None
    return _metrics_from_backtest(res)


def _fmt_row(label, m, base=None):
    def pct(key):
        v = m[key]
        return f"{v * 100:6.1f}%" if v is not None and np.isfinite(v) else "   n/a"

    def num(key):
        v = m[key]
        return f"{v:6.2f}" if v is not None and np.isfinite(v) else "   n/a"

    flag = ""
    if base is not None:
        better = (
            int(m["cagr"] >= base["cagr"])
            + int(m["sharpe"] >= base["sharpe"])
            + int(m["max_dd"] >= base["max_dd"])
        )
        flag = "  *" if better >= 2 else ""
    print(f"{label:<14}{pct('cagr'):>8}{num('sharpe'):>8}{num('sortino'):>9}"
          f"{pct('max_dd'):>9}{pct('last3yr'):>9}{pct('winrate'):>8}{flag}")


def main():
    print("Loading price data...")
    prices = data_loader.load_data()
    if prices is None or prices.empty:
        print("ERROR: no price data.")
        sys.exit(1)

    engine = BLEngine(prices)
    start = FAST_START or str(engine.asset_prices.index[0].date())
    end = str(engine.asset_prices.index[-1].date())
    print(f"Backtest window: {start} to {end}")
    print("Running baseline (this is the slow part)...")

    base = run_once(engine, start, end, {})
    if base is None:
        print("ERROR: baseline backtest failed.")
        sys.exit(1)

    all_rows = [{"parameter": "BASELINE", "value": "-", **base}]
    header = (f"{'value':<14}{'CAGR':>8}{'Sharpe':>8}{'Sortino':>9}"
              f"{'MaxDD':>9}{'Last3y':>9}{'WinRate':>8}")

    print("\nLegend: higher CAGR/Sharpe/Sortino better; MaxDD closer to 0 better;")
    print("Last3y = recent-bull catch-up; WinRate = share of years beating SPY.")
    print("'*' marks a variant that beats baseline on >=2 of CAGR/Sharpe/MaxDD.")

    for const, values in SWEEPS.items():
        base_val = getattr(eng, const)
        vals = sorted(set(values) | {base_val})
        print("\n" + "=" * 72)
        print(f"  {const}   (baseline = {base_val})")
        print("=" * 72)
        print(header)
        print("-" * 72)
        for v in vals:
            if v == base_val:
                _fmt_row(f"{v} (base)", base, None)
                all_rows.append({"parameter": const, "value": v, **base})
                continue
            print(f"  testing {const}={v} ...", flush=True)
            m = run_once(engine, start, end, {const: v})
            if m is None:
                print(f"{str(v):<14}(failed)")
                continue
            _fmt_row(str(v), m, base)
            all_rows.append({"parameter": const, "value": v, **m})

    pd.DataFrame(all_rows).to_csv("sweep_results.csv", index=False)
    print("\nSaved sweep_results.csv in backend/. Send it back and I'll help you read it.")


if __name__ == "__main__":
    main()
