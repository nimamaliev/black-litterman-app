# Black-Litterman Sector Allocation Engine

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![React](https://img.shields.io/badge/React-18-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Status](https://img.shields.io/badge/Status-Live-success)

A sector-allocation model for the 11 SPDR sector ETFs, built on a textbook
**Black-Litterman** setup: it starts from the market's own portfolio, blends in
a small number of explicit relative views, and wraps the result in a
volatility-targeting overlay that moves to cash when markets get turbulent.

**Live demo:** [https://black-litterman-app.vercel.app](https://black-litterman-app.vercel.app) *(free-tier backend: the first request can take ~60s)*

## How the model works

At every quarterly rebalance, using only data available on that date:

1. **Prior: market equilibrium.** The market portfolio is SPY. Its sector
   weights are inferred by returns-based style analysis: the non-negative
   weights, summing to 1, that best replicate SPY's last year of daily returns.
   Reverse optimisation turns them into implied excess returns
   `pi = delta * Sigma * w_mkt`, where `Sigma` is a Ledoit-Wolf covariance over
   two years and `delta = 5% equity premium / market variance`.
   With no views, the model simply holds `w_mkt`.
2. **Views.** Two relative views, each a long-top-3 / short-bottom-3 sector
   portfolio `P`:
   - **Low volatility:** low-vol sectors outperform high-vol sectors.
   - **Momentum + reversal:** strong 12-1 month momentum and a weak last month
     outperform the opposite.

   Each view's expected spread is `Q = P.pi + 0.25 * sqrt(P Sigma P')`. That is,
   the view expects the spread to beat its equilibrium value by a quarter of the
   spread's own volatility. Users can add absolute views ("XLK +3% over
   equilibrium") or relative views ("XLE beats XLK by 5%").
3. **Confidence.** `Omega = ((1 - c) / c) * tau * P Sigma P'`, with `tau = 0.05`,
   so `c = 0.5` is the He-Litterman default. A **logistic regression** predicts,
   from six regime features, whether each view's long/short portfolio will make
   money over the next quarter:
   - leadership strength
   - breadth
   - dispersion
   - average correlation
   - SPY 12m trend
   - SPY 6m volatility

   It is trained walk-forward, only on outcomes already known on the decision
   date, and scales `c` up or down relative to the view's historical hit rate.
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

**All parameters were chosen on 2007-2021 only.** 2022 onward was held out and
evaluated once, afterwards. `backend/research.py` enforces this split.

| Period | Strategy | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| Dev 2007-2021 | This model | 8.9% | 10.1% | 0.81 | -23.7% |
| | SPY with the same vol overlay | 7.9% | 10.3% | 0.72 | -23.8% |
| | BL portfolio, no overlay | 11.5% | 18.4% | 0.64 | -47.3% |
| | SPY buy & hold | 10.6% | 20.2% | 0.56 | -55.2% |
| **Hold-out 2022 to Jun 2026** | This model | 8.2% | 10.6% | 0.42 | -13.9% |
| | SPY with the same vol overlay | 9.2% | 10.7% | 0.50 | -13.9% |
| | BL portfolio, no overlay | 12.5% | 15.6% | 0.57 | -21.9% |
| | Market equilibrium (no views) | 12.4% | 17.5% | 0.53 | -24.4% |
| | SPY buy & hold | 12.1% | 17.6% | 0.51 | -24.5% |

What these numbers say:

- **The views held up out-of-sample.** The fully invested BL portfolio beat
  both the market equilibrium and SPY on a risk-adjusted basis in the hold-out,
  with a smaller drawdown.
- **The overlay is insurance, and it has a cost.** It roughly halves
  volatility and drawdowns. In the V-shaped 2022-2026 market, it cost more
  return than it saved. The backtest page has a toggle to switch it off.
- **The ML confidence model barely matters.** On the dev period it changes CAGR
  by about 0.1% a year and leaves Sharpe essentially unchanged. It is kept
  because modulating view confidence is the right place for it in a BL
  framework, but it should not be read as the source of the performance.
- **Hold-out does not mean live.** The hold-out period is cleaner than the dev
  period but still a backtest. Earlier versions of this project were evaluated
  on the full history, so some indirect influence can't be ruled out.

## Backtest mechanics and known limitations

**What the backtest gets right:**
- **Point-in-time decisions.** A decision for day X uses prices through the
  close before X and is held, drifting, until the next rebalance. Consecutive
  periods share their boundary close, so no days are dropped.
- **Realistic costs.** Costs are charged on the full notional traded, measured
  against the drifted weights.
- **Benchmarks on equal terms.** Every backtest also reports SPY, SPY with the
  same overlay, the BL portfolio without the overlay, the market equilibrium,
  inverse-vol sectors, equal-weight sectors and 60/40 SPY/IEF. They use the same
  dates and the same costs. The 60/40 row appears once IEF history has been
  downloaded.

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
`track-record` branch. The log is append-only and timestamped by git, so it
can't be back-filled quietly. The backend's `/track_record` endpoint and the
**Live Record** page measure performance going forward from each entry. The
record only starts once the workflow is on the default branch.

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
python research.py             # dev-period parameter sweeps
python research.py --holdout   # final config on dev + hold-out

cd frontend
npm install
npm run dev
```
