# Black-Litterman Sector Allocation Engine

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![React](https://img.shields.io/badge/React-18-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Status](https://img.shields.io/badge/Status-Live-success)

A sector-allocation model for the 11 SPDR sector ETFs, built on a textbook
**Black-Litterman** setup: it starts from the market's own portfolio, blends in
two explicit, rule-based relative views, and wraps the result in a
volatility-targeting overlay that moves to cash when markets get turbulent.

**What it is, and isn't.** It is a carefully built BL pipeline with a
defensive overlay. The overlay reliably cuts volatility and drawdowns. Whether
the sector views add excess return on top is **not statistically detectable**
in the data available; see [Results](#results-backtest-net-of-costs).

**Live demo:** [https://black-litterman-app.vercel.app](https://black-litterman-app.vercel.app).
The backend runs on a free instance that sleeps when idle. Opening the site
wakes it, so the first data can take a minute or two to appear, while it
starts and pre-computes. After that, requests take seconds.

## How the model works

At every quarterly rebalance, using only data available on that date:

1. **Prior: market equilibrium.** The market portfolio is SPY. Its sector
   weights are inferred by returns-based style analysis: the non-negative
   weights, summing to 1, that best replicate SPY's last year of daily returns.
   (The budget is imposed as a heavily weighted penalty row in NNLS. It matches
   an exact constrained solve to about 1e-9.) Reverse optimisation turns them
   into implied excess returns `pi = delta * Sigma * w_mkt`, where `Sigma` is a
   Ledoit-Wolf covariance over two years and
   `delta = 5% equity premium / market variance`. With no views, the model
   holds `w_mkt` exactly.
2. **Views.** Two relative views, each a long-top-3 / short-bottom-3 sector
   portfolio `P`:
   - **Low volatility:** low-vol sectors outperform high-vol sectors.
   - **Momentum + reversal:** strong 12-1 month momentum and a weak last month
     outperform the opposite.

   Each view's expected spread is `Q = P.pi + 0.25 * sqrt(P Sigma P')`. That is,
   the view expects the spread to beat its equilibrium value by a quarter of the
   spread's own volatility. Users can add absolute views ("XLK +3% over
   equilibrium") or relative views ("XLE beats XLK by 5%").
3. **Confidence.** `Omega = ((1 - c) / c) * tau * P Sigma P'`, with `c = 0.5`
   (the He-Litterman default).
   - **`tau` doesn't affect the portfolio.** Because `Omega` is proportional to
     `tau`, `tau` cancels out of the posterior mean exactly. It has no effect on
     the weights and only scales the posterior covariance used for the reported
     volatility. A unit test pins this. The confidence `c` is the only knob that
     moves the portfolio.
   - **Optional ML confidence model, off by default.** A logistic regression can
     scale `c` by predicting whether each view will pay off next quarter. It is
     trained walk-forward on six regime features. With 63-day labels sampled
     every 21 days, the labels overlap, and the training set holds roughly a
     dozen independent observations when the model first switches on. That is
     too few to estimate six coefficients, and it changed nothing measurable on
     2007-2021. It stays in the code as an experiment (`ML_ENABLED`).
4. **Posterior and optimisation.** The standard BL posterior mean feeds a
   long-only mean-variance utility maximisation with risk aversion `delta`.
   Constraints: at most 40% per sector, and at most ±10 points from each
   sector's market weight.
5. **Defensive overlay.** Daily exposure is scaled so trailing 21-day realised
   volatility stays near 10% a year, and the rest earns the T-bill rate (^IRX).
   There is no leverage and no shorting. Exposure changes only when the target
   moves more than 5 points, and every change pays trading costs.

## Results (backtest, net of costs)

The cost is 5 bps per unit of notional traded, on sector trades and overlay
changes alike.

Parameters were chosen on 2007-2021 (dev). 2022 onward was held out.

**One honest caveat:** after the hold-out had been viewed once, the ML
confidence model was switched off. That decision rested on dev-period evidence,
but it means the current configuration's hold-out numbers are **post-hoc**. The
first, clean look is shown alongside. Every look at the hold-out is recorded in
[`backend/research_holdout_log.jsonl`](backend/research_holdout_log.jsonl)
with the exact configuration used.

| Period | Strategy | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| Dev 2007-2021 | This model | 8.8% | 10.1% | 0.81 | -23.7% |
| | SPY with the same vol overlay | 7.9% | 10.3% | 0.72 | -23.8% |
| | BL portfolio, no overlay | 11.4% | 18.4% | 0.64 | -47.3% |
| | Market equilibrium (no views) | 10.7% | 20.0% | 0.57 | -54.2% |
| | SPY buy & hold | 10.6% | 20.2% | 0.56 | -55.2% |
| Hold-out 2022 to Jun 2026, current config (post-hoc) | This model | 8.8% | 10.6% | 0.48 | -12.7% |
| | SPY with the same vol overlay | 9.2% | 10.7% | 0.50 | -13.9% |
| | BL portfolio, no overlay | 13.2% | 15.8% | 0.62 | -20.0% |
| | Market equilibrium (no views) | 12.4% | 17.5% | 0.53 | -24.4% |
| | SPY buy & hold | 12.1% | 17.6% | 0.51 | -24.5% |
| Hold-out, first look (ML on, clean) | This model | 8.2% | 10.6% | 0.42 | -13.9% |
| | BL portfolio, no overlay | 12.5% | 15.6% | 0.57 | -21.9% |

**Is any of this signal?** Block-bootstrap 90% intervals (21-day blocks, 2,000
resamples) for differences in Sharpe ratio:

| Comparison | Dev 2007-2021 | Hold-out 2022-2026 |
|---|---|---|
| This model vs SPY with the same overlay | +0.09 (-0.01 to +0.20) | -0.02 (-0.27 to +0.22) |
| BL no overlay vs market equilibrium (what the views add) | +0.07 (-0.01 to +0.15) | +0.09 (-0.13 to +0.29) |
| BL no overlay vs SPY | +0.08 (-0.00 to +0.17) | +0.10 (-0.12 to +0.31) |

What these numbers support:

- **No detectable edge from the views in either direction.** On dev, the views
  look mildly positive, with intervals just touching zero. The hold-out is one
  4.5-year regime, and its intervals are wide enough to be consistent with
  both "the views add nothing" and "the views add something small". Neither
  "it works" nor "it lost" is supported.
- **The overlay works as insurance, at a price.** In the hold-out it cut the
  max drawdown from about -20% to -13% and volatility from about 16% to 11%,
  and cost about 4.4 points of CAGR in a V-shaped market. The backtest page can
  switch it off.
- **Backtests are not live results.** Earlier versions of this project were
  evaluated on the full history, so some indirect influence on design choices
  can't be ruled out. The live track record is the real test.

## Backtest mechanics and known limitations

**What the backtest gets right (each item has a unit test):**
- **Point-in-time decisions.** A decision for day X uses prices through the
  close before X and is held, drifting, until the next rebalance. Consecutive
  periods share their boundary close, so no days are dropped. Skipped
  (low-turnover) rebalances keep drifting.
- **Realistic costs.** Costs are charged on the full notional traded, measured
  against the drifted weights.
- **Benchmarks on equal terms.** Every backtest also reports SPY, SPY with the
  same overlay, the BL portfolio without the overlay, the market equilibrium,
  inverse-vol sectors, equal-weight sectors and 60/40 SPY/IEF. They use the same
  dates and the same costs.

**The dev/hold-out split is a convention, not a guarantee.** Nothing in code can
stop someone from looking at the hold-out and then changing `engine.py`.
`research.py` makes that visible:
- Every `--holdout` run appends the full engine configuration and its hash to
  the committed log.
- It warns loudly when the hold-out has already been seen under a different
  configuration.

**Limitations:**
- **Back-filled history.** XLC (launched 2018) and XLRE (2015) are back-filled
  with VOX and VNQ, which are related but not identical exposures.
- **Approximate market weights.** The weights inferred from SPY's returns are
  an estimate. They are noisy for highly correlated sectors, and some small
  sectors can come out at 0%.
- **Hindsight in the setup.** Choosing the 11 sector ETFs as the universe, and
  low-vol and momentum as view families, are decisions made with knowledge of
  the published literature on those effects.
- **Data source.** Prices come from Yahoo Finance via `yfinance`, with adjusted
  closes.

## Live track record

`.github/workflows/track-record.yml` runs every weekday after the US close. It
appends the model's current recommendation (sector weights and invested
fraction) to `backend/track_record/recommendations.csv` on the separate
`track-record` branch. The backend's `/track_record` endpoint and the
**Live Record** page measure performance going forward from each entry.

**How much to trust the log.** It is append-only by convention, with checks:
- **History check.** Each run verifies that every past version of the CSV only
  ever gained rows at the end (`backend/verify_track_record.py`), and fails
  otherwise.
- **Independent record.** Each run writes the file's SHA-256 into the run
  summary, so GitHub's Actions history independently records what the file
  looked like each day.
- **Branch protection.** The `track-record` branch is meant to block
  force-pushes and deletion.

Even so, this is not cryptographic tamper-evidence. Someone with admin rights
could disable the protection and rewrite history consistently, and git
timestamps can be set to anything. Real notarisation would need an external
anchor such as OpenTimestamps.

## Tech stack

- **Backend:** Python, FastAPI, NumPy, pandas, SciPy, cvxpy, PyPortfolioOpt
  (Ledoit-Wolf covariance), scikit-learn.
- **Frontend:** React, Vite, Recharts, Tailwind CSS.
- **Data:** Yahoo Finance (`yfinance`), cached in `backend/app/data/prices.parquet`.

## Running locally

```bash
cd backend
pip install -r requirements.txt
python main.py                 # API on :8000
pytest -q                      # unit tests (synthetic data, no network)
python research.py             # dev-period sweeps and bootstrap intervals
python research.py --holdout   # also the hold-out (logged)

cd frontend
npm install
npm run dev
```
