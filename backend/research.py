"""research.py - parameter research with an enforced development / hold-out split.

Every sweep below runs ONLY on the development period (DEV_START..DEV_END).
The hold-out period (HOLDOUT_START onward) is evaluated once, for the final
configuration, and only when you pass --holdout. Tuning anything after looking
at the hold-out numbers turns them into in-sample numbers, so don't.

Run from backend/:

    python research.py              # dev-period sweeps
    python research.py --holdout    # final config on dev AND hold-out

Uses the cached prices in app/data/prices.parquet (no network needed).
"""
import argparse
import logging
import sys

import pandas as pd

import app.engine as eng
from app import data_loader

DEV_START, DEV_END = "2007-01-01", "2021-12-31"
HOLDOUT_START = "2022-01-01"

# One-at-a-time sweeps around the current engine defaults.
SWEEPS = {
    "VIEW_SIGNALS": [("mom_12_1",), ("mom_rev",), ("low_vol",), ("low_vol", "mom_rev")],
    "VIEW_IR": [0.25, 0.5, 1.0],
    "REBALANCE_FREQ": [21, 63],
    "ML_ENABLED": [True, False],
    "ACTIVE_LIMIT": [0.05, 0.10, 0.20],
    "VOL_TARGET": [0.10, 0.12, 0.15],
}


def run(prices, start, end, overrides=None):
    overrides = overrides or {}
    saved = {k: getattr(eng, k) for k in overrides}
    try:
        for k, v in overrides.items():
            setattr(eng, k, v)
        e = eng.BLEngine(prices)
        return e.run_backtest(start, end, [])
    finally:
        for k, v in saved.items():
            setattr(eng, k, v)


def table(res, title):
    print(f"\n=== {title} ===")
    print(f"{'strategy':38s} {'CAGR':>7s} {'Vol':>7s} {'Sharpe':>7s} {'MaxDD':>8s}")
    for b in res["benchmarks"]:
        print(f"{b['name']:38s} {b['cagr']:7.1%} {b['volatility']:7.1%} {b['sharpe']:7.2f} {b['max_dd']:8.1%}")
    m = res["metrics"]
    print(f"avg exposure {m['avg_exposure']:.0%} | sector turnover {m['sector_turnover']:.1f}x/yr"
          f" | ML active {m['ml_active_share']:.0%} of rebalances")


def by_name(res, name):
    return next(b for b in res["benchmarks"] if b["name"] == name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="also evaluate the hold-out period")
    ap.add_argument("--no-sweep", action="store_true", help="skip the dev-period sweeps")
    args = ap.parse_args()

    logging.disable(logging.WARNING)
    prices = data_loader.read_prices()
    if prices.empty:
        sys.exit("No cached prices found in app/data/prices.parquet")

    base = run(prices, DEV_START, DEV_END)
    table(base, f"DEV {DEV_START}..{DEV_END} - current defaults")

    if not args.no_sweep:
        print("\nOne-at-a-time sweeps on DEV (Sharpe / CAGR / MaxDD):")
        print(f"{'param=value':28s} {'model':>22s} {'no overlay':>22s}")
        for param, values in SWEEPS.items():
            for v in values:
                r = run(prices, DEV_START, DEV_END, {param: v})
                a = by_name(r, "Black-Litterman (this model)")
                b = by_name(r, "Black-Litterman, no overlay")
                cur = " *" if getattr(eng, param) == v else ""
                print(f"{param + '=' + str(v):28s} "
                      f"{a['sharpe']:6.2f} {a['cagr']:6.1%} {a['max_dd']:7.1%}  "
                      f"{b['sharpe']:6.2f} {b['cagr']:6.1%} {b['max_dd']:7.1%}{cur}")

    if args.holdout:
        end = str(prices.index.max().date())
        hold = run(prices, HOLDOUT_START, end)
        table(hold, f"HOLD-OUT {HOLDOUT_START}..{end} - evaluate once, do not tune on this")


if __name__ == "__main__":
    main()
