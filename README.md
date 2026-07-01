# AI-Driven Black-Litterman Asset Allocation Engine

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![React](https://img.shields.io/badge/React-18-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95-green)
![Status](https://img.shields.io/badge/Status-Live-success)

```markdown
# AI-Driven Black-Litterman Asset Allocation Engine

!Python
!React
!FastAPI
!Status

## Project Overview
This project is a **Hybrid Asset Allocation Framework** that bridges Classical Financial Theory (Black-Litterman) with Modern Machine Learning.

Unlike standard trading bots that are unstable, this engine anchors to a market-equilibrium portfolio (Risk Parity) and "tilts" allocations only when a Logistic Regression model identifies high-confidence regime shifts.

**Live Demo:** https://black-litterman-app.vercel.app  (Note: Free tier hosting may require ~60s cold start)

## Core Logic

### 1. Anchor & Tilt Philosophy
- **The Anchor:** Uses **inverse-volatility weighting** (a simplified risk-based anchor; note this is not full risk parity / ERC, as it ignores cross-asset correlations) to calculate a diversified market-equilibrium portfolio.
- **The Tilt:** Uses **Black-Litterman** optimization to mathematically blend the anchor with active views derived from Machine Learning predictions.

### 2. The AI "Brain"
A **Logistic Regression** classifier scans market conditions to generate confidence scores (0-100%):
- **Regime Detection:** Adjusts risk tolerance based on volatility clusters.
- **Momentum Scanner:** Measures 12-month trend strength relative to SPY.
- **Confidence Scoring:** The model's probability output determines the magnitude of the portfolio tilt.

### 3. Bias-Free Backtesting
- **Strict Point-in-Time Data:** Training windows (504 days) strictly precede the decision date. No future data leakage.
- **Walk-Forward Validation:** Simulates quarterly rebalancing by "walking forward" through historical data.
- **Real-World Friction:** Accounts for transaction costs (5bps) and simulates "Drift" (Buy-and-Hold) between rebalance periods.

## Tech Stack
- **Backend:** Python, FastAPI, NumPy, Pandas, PyPortfolioOpt, Scikit-Learn.
- **Frontend:** React, Vite, Recharts, TailwindCSS.
- **Data:** Yahoo Finance API (yfinance) with robust caching and timezone handling.

## Installation

### Backend
    cd backend
    pip install -r requirements.txt
    python main.py

### Frontend
    cd frontend
    npm install
    npm run dev
```
npm install
npm run dev
