"""research.py - parameter research on a development / hold-out split.

Sweeps run ONLY on the development period (DEV_START..DEV_END). The hold-out
period (HOLDOUT_START onward) is evaluated only with --holdout.

This is a convention, not a guarantee: nothing in code can stop someone from
looking at the hold-out and then changing engine.py. What this script does is
make that visible. Every --holdout run appends the full engine configuration
(and its hash) to research_holdout_log.jsonl, which is committed to the repo,
and warns loudly when the hold-out has already been viewed under a different
configuration - from then on, hold-out numbers for the new configuration are
not out-of-sample and must be reported as such.

Each window also reports a block-bootstrap interval for the difference in
Sharpe ratio between key strategy pairs, because a single 4-5 year window is
one realisation and small Sharpe differences are usually noise.

Run from backend/:

    python research.py              # dev-period sweeps + dev intervals
    python research.py --holdout    # also the hold-out (logged)

Uses the cached prices in app/data/prices.parquet (no network needed).
"""
import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import app.engine as eng
from app import data_loader

DEV_START, DEV_END = "2007-01-01", "2021-12-31"
HOLDOUT_START = "2022-01-01"
HOLDOUT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "research_holdout_log.jsonl")

# Sharpe-difference intervals: (strategy, comparator) pairs from the benchmark table.
PAIRS = [
    ("Black-Litterman (this model)", "SPY with the same vol overlay"),
    ("Black-Litterman, no overlay", "Market equilibrium (no views)"),
    ("Black-Litterman, no overlay", "SPY buy & hold"),
]
BOOT_REPS = 2000
BOOT_BLOCK = 21          # trading days per block (keeps a month of autocorrelation)

# One-at-a-time sweeps around the current engine defaults.
SWEEPS = {
    "VIEW_SIGNALS": [("mom_12_1",), ("mom_rev",), ("low_vol",), ("low_vol", "mom_rev")],
    "VIEW_IR": [0.25, 0.5, 1.0],
    "REBALANCE_FREQ": [21, 63],
    "ML_ENABLED": [True, False],
    "ACTIVE_LIMIT": [0.05, 0.10, 0.20],
    "VOL_TARGET": [0.10, 0.12, 0.15],
}


def engine_config():
    """All simple module-level settings of the engine, and a short hash of them."""
    cfg = {}
    for k in sorted(dir(eng)):
        v = getattr(eng, k)
        if k.isupper() and isinstance(v, (int, float, str, bool, tuple, type(None))):
            cfg[k] = list(v) if isinstance(v, tuple) else v
    digest = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
    return cfg, digest


def check_and_log_holdout(data_end, results):
    """Warn if the hold-out was already viewed under another config; append this run."""
    cfg, digest = engine_config()
    previous = []
    if os.path.exists(HOLDOUT_LOG):
        with open(HOLDOUT_LOG) as f:
            previous = [json.loads(line) for line in f if line.strip()]
    others = [p for p in previous if p["config_hash"] != digest]
    if others:
        bar = "!" * 78
        print(f"\n{bar}\nWARNING: the hold-out was already viewed under {len(set(p['config_hash'] for p in others))}"
              f" other configuration(s), first on {others[0]['viewed_at_utc'][:10]}.\n"
              f"Hold-out results for config {digest} are NOT out-of-sample: any change made\n"
              f"after that first look may have been influenced by it. Report them as post-hoc.\n{bar}")
    entry = {"viewed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "config_hash": digest, "data_end": data_end, "config": cfg, "results": results}
    with open(HOLDOUT_LOG, "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"(hold-out view logged to {os.path.basename(HOLDOUT_LOG)}, config {digest})")


def _sharpe(r, rf):
    ex = r - rf
    sd = ex.std()
    return float(ex.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0


def sharpe_diff_interval(a, b, rf, reps=BOOT_REPS, block=BOOT_BLOCK, seed=0):
    """Circular block bootstrap of Sharpe(a) - Sharpe(b) on paired daily returns.

    Returns (observed difference, 5th pct, 95th pct, share of resamples > 0)."""
    df = pd.concat([a, b, rf], axis=1).dropna()
    x = df.to_numpy()
    n = len(x)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    diffs = np.empty(reps)
    for k in range(reps):
        starts = rng.integers(0, n, n_blocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n] % n
        s = x[idx]
        ea, eb = s[:, 0] - s[:, 2], s[:, 1] - s[:, 2]
        diffs[k] = (ea.mean() / ea.std() - eb.mean() / eb.std()) * np.sqrt(252)
    obs = _sharpe(df.iloc[:, 0], df.iloc[:, 2]) - _sharpe(df.iloc[:, 1], df.iloc[:, 2])
    return obs, float(np.percentile(diffs, 5)), float(np.percentile(diffs, 95)), float((diffs > 0).mean())


def intervals(res, title):
    print(f"\nSharpe differences, {title} (block bootstrap, {BOOT_REPS} resamples, {BOOT_BLOCK}-day blocks):")
    out = {}
    for a, b in PAIRS:
        obs, lo, hi, pos = sharpe_diff_interval(res["series"][a], res["series"][b], res["rf_daily"])
        print(f"  {a} vs {b}: {obs:+.2f}  [90% CI {lo:+.2f} .. {hi:+.2f}]  P(>0) {pos:.0%}")
        out[f"{a} vs {b}"] = {"diff": round(obs, 3), "ci90": [round(lo, 3), round(hi, 3)], "p_pos": round(pos, 3)}
    return out


def run(prices, start, end, overrides=None):
    overrides = overrides or {}
    saved = {k: getattr(eng, k) for k in overrides}
    try:
        for k, v in overrides.items():
            setattr(eng, k, v)
        e = eng.BLEngine(prices)
        return e.run_backtest(start, end, [], return_series=True)
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
    intervals(base, "dev")

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
        table(hold, f"HOLD-OUT {HOLDOUT_START}..{end} - do not tune on this")
        ci = intervals(hold, "hold-out")
        summary = {b["name"]: {k: round(b[k], 4) for k in ("cagr", "volatility", "sharpe", "max_dd")}
                   for b in hold["benchmarks"]}
        check_and_log_holdout(end, {"benchmarks": summary, "sharpe_diff": ci})


if __name__ == "__main__":
    main()
