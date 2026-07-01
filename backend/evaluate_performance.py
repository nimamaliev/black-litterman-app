"""evaluate_performance.py

Standalone performance report for the Black-Litterman strategy.

Run it from the backend/ folder (the same place you run the server and pytest):

    cd backend
    python evaluate_performance.py

What it does:
  * Loads your cached price data (and refreshes it from Yahoo Finance if the
    cache is more than a few days old).
  * Runs the engine's backtest over the FULL available history, with no manual
    views (so you see the model's own, baseline skill).
  * Prints a plain-language report comparing the strategy to simply holding SPY:
    headline metrics, a year-by-year table, and how it held up in specific
    market regimes (2008 crash, COVID, 2022, recent years).
  * Saves equity_curve.csv and yearly_returns.csv next to this script so you can
    drop the numbers straight into a thesis or spreadsheet.

It does NOT change any app code; it only reads the engine and your price data.
"""

import sys
import numpy as np
import pandas as pd

from app import data_loader
from app.engine import BLEngine


def _to_series(dates, values):
    idx = pd.to_datetime(pd.Index(dates))
    return pd.Series(values, index=idx, dtype=float)


def _period_metrics(curve, rf_ann=0.0):
    """Compute return/risk metrics for a value curve (a pandas Series)."""
    curve = curve.dropna()
    if len(curve) < 2:
        return None
    rets = curve.pct_change().dropna()
    years = (curve.index[-1] - curve.index[0]).days / 365.25
    total_return = curve.iloc[-1] / curve.iloc[0] - 1.0
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    ann_vol = rets.std() * np.sqrt(252)
    sharpe = (rets.mean() * 252 - rf_ann) / ann_vol if ann_vol > 0 else 0.0
    downside = rets[rets < 0]
    dd_dev = downside.std() * np.sqrt(252)
    sortino = (rets.mean() * 252 - rf_ann) / dd_dev if dd_dev > 0 else 0.0
    running_max = curve.cummax()
    max_dd = float((curve / running_max - 1).min())
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    return {
        "total_return": total_return,
        "cagr": cagr,
        "vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_dd": max_dd,
        "calmar": calmar,
    }


def _pct(x):
    return f"{x * 100:6.1f}%" if x is not None and np.isfinite(x) else "   n/a"


def _num(x):
    return f"{x:6.2f}" if x is not None and np.isfinite(x) else "   n/a"


def main():
    print("Loading price data (may refresh from Yahoo Finance)...")
    prices = data_loader.load_data()
    if prices is None or prices.empty:
        print("ERROR: no price data available.")
        sys.exit(1)

    engine = BLEngine(prices)
    start = str(engine.asset_prices.index[0].date())
    end = str(engine.asset_prices.index[-1].date())
    print(f"Data covers {start} to {end} ({len(engine.asset_prices)} trading days).")
    print("Running full-history backtest (baseline model, no manual views)...\n")

    res = engine.run_backtest(start, end, [])
    if "error" in res:
        print("ERROR:", res["error"])
        sys.exit(1)

    rf_ann = res["metrics"].get("risk_free", 0.0)
    port = _to_series(res["dates"], res["portfolio"])
    spy = _to_series(res["dates"], res["spy"])

    pm = _period_metrics(port, rf_ann)
    sm = _period_metrics(spy, rf_ann)

    print("=" * 66)
    print("  PLAIN-LANGUAGE SUMMARY")
    print("=" * 66)
    print(res["summary"])
    print()

    print("=" * 66)
    print(f"  HEADLINE METRICS  ({port.index[0].date()} to {port.index[-1].date()})")
    print("=" * 66)
    header = f"{'Metric':<22}{'Strategy':>12}{'SPY':>12}{'Diff':>12}"
    print(header)
    print("-" * len(header))

    def row(label, key, pct=True):
        sv, bv = pm[key], sm[key]
        edge = (sv - bv) if (sv is not None and bv is not None) else None
        fmt = _pct if pct else _num
        print(f"{label:<22}{fmt(sv):>12}{fmt(bv):>12}{fmt(edge):>12}")

    row("Total return", "total_return")
    row("CAGR (per year)", "cagr")
    row("Annualized vol", "vol")
    row("Sharpe ratio", "sharpe", pct=False)
    row("Sortino ratio", "sortino", pct=False)
    row("Max drawdown", "max_dd")
    row("Calmar ratio", "calmar", pct=False)
    print(f"\nRisk-free rate used (avg ^IRX): {_pct(rf_ann)}")

    print("\n" + "=" * 66)
    print("  YEAR-BY-YEAR")
    print("=" * 66)
    print(f"{'Year':<6}{'Strategy':>11}{'SPY':>10}{'Diff':>10}   Top holdings")
    print("-" * 66)
    wins = 0
    yt = res["yearly_table"]
    for r in yt:
        if r["diff"] > 0:
            wins += 1
        print(f"{r['year']:<6}{_pct(r['portfolio']):>11}{_pct(r['spy']):>10}"
              f"{_pct(r['diff']):>10}   {r.get('top_holdings', '')}")
    n = len(yt)
    print("-" * 66)
    if n:
        print(f"Beat SPY in {wins} of {n} years ({wins / n * 100:.0f}%).")
        best = max(yt, key=lambda r: r["portfolio"])
        worst = min(yt, key=lambda r: r["portfolio"])
        print(f"Best year:  {best['year']} ({_pct(best['portfolio']).strip()})")
        print(f"Worst year: {worst['year']} ({_pct(worst['portfolio']).strip()})")

    print("\n" + "=" * 66)
    print("  KEY PERIODS (how it held up in specific regimes)")
    print("=" * 66)
    last = port.index[-1]
    periods = [
        ("Global Financial Crisis", "2007-10-01", "2009-03-31"),
        ("Post-GFC bull 2009-2019", "2009-01-01", "2019-12-31"),
        ("COVID crash", "2020-02-19", "2020-03-23"),
        ("2022 bear market", "2022-01-01", "2022-10-12"),
        ("Last 1 year", str((last - pd.Timedelta(days=365)).date()), end),
        ("Last 3 years", str((last - pd.Timedelta(days=365 * 3)).date()), end),
        ("Last 5 years", str((last - pd.Timedelta(days=365 * 5)).date()), end),
    ]
    print(f"{'Period':<26}{'Strat ret':>11}{'SPY ret':>10}{'Strat DD':>11}{'SPY DD':>9}")
    print("-" * 67)
    for name, s, e in periods:
        ps = port.loc[(port.index >= s) & (port.index <= e)]
        ss = spy.loc[(spy.index >= s) & (spy.index <= e)]
        pmm = _period_metrics(ps)
        smm = _period_metrics(ss)
        if not pmm or not smm:
            print(f"{name:<26}{'(no data)':>11}")
            continue
        print(f"{name:<26}{_pct(pmm['total_return']):>11}{_pct(smm['total_return']):>10}"
              f"{_pct(pmm['max_dd']):>11}{_pct(smm['max_dd']):>9}")

    out = pd.DataFrame({"Strategy": port, "SPY": spy})
    out.index.name = "date"
    out.to_csv("equity_curve.csv")
    pd.DataFrame(yt).to_csv("yearly_returns.csv", index=False)
    print("\nSaved equity_curve.csv and yearly_returns.csv in the backend/ folder.")
    print("Done.")


if __name__ == "__main__":
    main()
