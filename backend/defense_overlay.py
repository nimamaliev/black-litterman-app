"""defense_overlay.py

External crash-defense overlay tester for the Black-Litterman strategy.

This file does NOT modify the engine or any app code. It runs ONE baseline
backtest, then post-processes the daily strategy returns with risk-management
overlays to see whether they improve crash-time and risk-adjusted metrics:

  1. Volatility targeting - scale exposure so trailing realized vol ~ a target.
  2. Trend filter         - cut exposure when SPY is below its long-run SMA.
  3. Combined             - stack both (multiply the two exposures).

The un-invested fraction earns the daily risk-free rate. No leverage and no
shorting: exposure is clamped to [EXPOSURE_FLOOR, EXPOSURE_CAP]. Every signal is
lagged one day to avoid look-ahead. The trend SMA is built from the engine's
full SPY history, so it is already 'warmed up' at the backtest start.

Run from the backend/ folder:

    cd backend
    python defense_overlay.py

It prints two tables (core risk-adjusted metrics + per-crash returns) comparing
the baseline against each overlay, and writes defense_results.csv.

NOTE: a single full-history backtest runs first and takes a minute or two; the
overlays themselves are instant (they just reshape the daily returns). For quick
iteration set FAST_START to a later date, e.g. "2007-01-01".
"""

import sys
import numpy as np
import pandas as pd

from app import data_loader
import app.engine as eng
from app.engine import BLEngine

FAST_START = None  # e.g. "2007-01-01"; None = full available history

# ---- Overlay parameter grids ------------------------------------------------
VOL_LOOKBACK = 21               # trading days for the realized-vol estimate
VOL_TARGETS = [0.10, 0.12, 0.15]  # annualized target vols to try
TREND_LOOKBACKS = [150, 200]    # SPY SMA windows for the trend filter
COMBO_VOL_TARGET = 0.12         # vol target used in the combined overlays
EXPOSURE_FLOOR = 0.0            # min exposure (0 = may go fully to cash)
EXPOSURE_CAP = 1.0             # max exposure (1 = no leverage)

# Crash / stress windows to score explicitly (inclusive date ranges).
CRASH_WINDOWS = {
    "GFC 07-09": ("2007-10-09", "2009-03-09"),
    "COVID 20":  ("2020-02-19", "2020-03-23"),
    "2022 bear": ("2022-01-03", "2022-10-12"),
}


def ann_metrics(rets, rf_daily):
    rets = rets.dropna()
    if rets.empty:
        return {}
    eq = (1 + rets).cumprod()
    years = len(rets) / 252.0
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = rets.std() * np.sqrt(252)
    rf_ann = rf_daily.reindex(rets.index).fillna(0.0).mean() * 252
    sharpe = (rets.mean() * 252 - rf_ann) / vol if vol > 0 else 0.0
    dn = rets[rets < 0].std() * np.sqrt(252)
    sortino = (rets.mean() * 252 - rf_ann) / dn if dn and dn > 0 else 0.0
    max_dd = float((eq / eq.cummax() - 1).min())
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    return {"cagr": cagr, "vol": vol, "sharpe": sharpe,
            "sortino": sortino, "max_dd": max_dd, "calmar": calmar}


def crash_returns(eq):
    out = {}
    for name, (s, e) in CRASH_WINDOWS.items():
        seg = eq.loc[(eq.index >= s) & (eq.index <= e)]
        out[name] = (seg.iloc[-1] / seg.iloc[0] - 1) if len(seg) > 1 else np.nan
    return out


def vol_target_exposure(strat_rets, target_vol):
    realized = strat_rets.rolling(VOL_LOOKBACK).std() * np.sqrt(252)
    exp = (target_vol / realized).shift(1)        # lag one day, no look-ahead
    return exp.clip(EXPOSURE_FLOOR, EXPOSURE_CAP).fillna(EXPOSURE_CAP)


def trend_exposure(spy, index, lookback):
    sma = spy.rolling(lookback).mean()
    raw = (spy > sma).astype(float)               # 1 = invested, 0 = to cash
    exp = raw.shift(1).reindex(index).ffill().fillna(EXPOSURE_CAP)
    return exp.clip(EXPOSURE_FLOOR, EXPOSURE_CAP)


def apply_overlay(strat_rets, exposure, rf_daily):
    exposure = exposure.reindex(strat_rets.index).fillna(EXPOSURE_CAP)
    rf = rf_daily.reindex(strat_rets.index).fillna(0.0)
    return exposure * strat_rets + (1 - exposure) * rf


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
    print("Running baseline backtest (the slow part, one run)...", flush=True)

    res = engine.run_backtest(start, end, [])
    if isinstance(res, dict) and "error" in res:
        print("ERROR: baseline backtest failed:", res.get("error"))
        sys.exit(1)

    dates = pd.to_datetime(pd.Index(res["dates"]))
    port = pd.Series(res["portfolio"], index=dates, dtype=float)
    strat_rets = port.pct_change().dropna()
    rf_daily = engine.rf_daily.reindex(strat_rets.index).fillna(0.0)
    spy = engine.market_prices.astype(float)

    # Build the exposure series for every variant.
    variants = {"Baseline (100% invested)": pd.Series(EXPOSURE_CAP, index=strat_rets.index)}
    for tv in VOL_TARGETS:
        variants[f"VolTarget {int(tv * 100)}%"] = vol_target_exposure(strat_rets, tv)
    for lb in TREND_LOOKBACKS:
        variants[f"Trend SMA{lb}"] = trend_exposure(spy, strat_rets.index, lb)
    for lb in TREND_LOOKBACKS:
        ve = vol_target_exposure(strat_rets, COMBO_VOL_TARGET)
        te = trend_exposure(spy, strat_rets.index, lb)
        variants[f"Combo {int(COMBO_VOL_TARGET * 100)}%+SMA{lb}"] = ve * te

    base_rets = apply_overlay(strat_rets, variants["Baseline (100% invested)"], rf_daily)
    base_m = ann_metrics(base_rets, rf_daily)

    # ---- Table 1: core risk-adjusted metrics --------------------------------
    print("\nLegend: higher CAGR/Sharpe/Sortino/Calmar better; Vol lower better;")
    print("MaxDD closer to 0 better; AvgExp = average equity exposure;")
    print("'*' = beats baseline on BOTH Sharpe and MaxDD.\n")
    h = (f"{'variant':<22}{'CAGR':>7}{'Vol':>7}{'Sharpe':>8}{'Sortino':>9}"
         f"{'MaxDD':>8}{'Calmar':>8}{'AvgExp':>8}")
    print(h)
    print("-" * len(h))

    rows = []
    for name, exp in variants.items():
        r = apply_overlay(strat_rets, exp, rf_daily)
        m = ann_metrics(r, rf_daily)
        eq = (1 + r).cumprod()
        cr = crash_returns(eq)
        avg_exp = exp.reindex(strat_rets.index).fillna(EXPOSURE_CAP).mean()
        flag = ""
        if name != "Baseline (100% invested)":
            if m["sharpe"] >= base_m["sharpe"] and m["max_dd"] >= base_m["max_dd"]:
                flag = "  *"
        print(f"{name:<22}{m['cagr'] * 100:6.1f}%{m['vol'] * 100:6.1f}%"
              f"{m['sharpe']:8.2f}{m['sortino']:9.2f}{m['max_dd'] * 100:7.1f}%"
              f"{m['calmar']:8.2f}{avg_exp:8.2f}{flag}")
        rows.append({"variant": name, **m, "avg_exposure": avg_exp, **cr})

    # ---- Table 2: per-crash returns -----------------------------------------
    print("\nReturn through each stress window (less negative = better defense):")
    ch = f"{'variant':<22}" + "".join(f"{k:>12}" for k in CRASH_WINDOWS)
    print("\n" + ch)
    print("-" * len(ch))
    for row in rows:
        print(f"{row['variant']:<22}" +
              "".join(f"{row[k] * 100:11.1f}%" if pd.notna(row[k]) else f"{'n/a':>12}"
                      for k in CRASH_WINDOWS))

    pd.DataFrame(rows).to_csv("defense_results.csv", index=False)
    print("\nSaved defense_results.csv in backend/. Send it back and I'll read it.")


if __name__ == "__main__":
    main()
