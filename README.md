# AI-Driven Black-Litterman Asset Allocation Engine

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![React](https://img.shields.io/badge/React-18-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95-green)
![Status](https://img.shields.io/badge/Status-Live-success)

## 📊 Project Overview
This project is a **Hybrid Asset Allocation Framework** that bridges Classical Financial Theory (Black-Litterman) with Modern Machine Learning.

Unlike standard trading bots that are unstable, this engine anchors to a market-equilibrium portfolio (Risk Parity) and "tilts" allocations only when a Logistic Regression model identifies high-confidence regime shifts.

**Live Demo:** [https://black-litterman-app.vercel.app](https://black-litterman-app.vercel.app) *(Note: Free tier hosting may require ~60s cold start)*

## 🧠 Core Logic

### 1. Anchor & Tilt Philosophy
- **The Anchor:** Uses **Risk Parity** to calculate a diversified market-equilibrium portfolio. This ensures safety and diversification by default.
- **The Tilt:** Uses **Black-Litterman** optimization to mathematically blend the anchor with active views derived from Machine Learning predictions.

### 2. The AI "Brain"
A **Logistic Regression** classifier scans market conditions to generate confidence scores (0-100%):
- **Regime Detection:** Adjusts risk tolerance based on volatility clusters.
- **Momentum Scanner:** Measures 12-month trend strength relative to SPY.
- **Confidence Scoring:** The model's probability output determines the *magnitude* of the portfolio tilt.

### 3. Bias-Free Backtesting
A custom-built backtesting engine designed to eliminate common quantitative pitfalls:
- **Strict Point-in-Time Data:** Training windows (504 days) strictly precede the decision date. No future data leakage.
- **Walk-Forward Validation:** Simulates quarterly rebalancing by "walking forward" through historical data.
- **Real-World Friction:** Accounts for transaction costs (5bps) and simulates "Drift" (Buy-and-Hold) between rebalance periods to capture compound growth.

## 🛠️ Tech Stack
- **Backend:** Python, FastAPI, NumPy, Pandas, PyPortfolioOpt, Scikit-Learn.
- **Frontend:** React, Vite, Recharts, TailwindCSS.
- **Data:** Yahoo Finance API (yfinance) with robust caching and timezone handling.

## 🚀 Installation

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
