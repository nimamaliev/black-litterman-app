import pandas as pd
import numpy as np
import yfinance as yf
from pypfopt import black_litterman, risk_models, EfficientFrontier
import warnings
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")

# ==========================================
# CONSTANTS & CONFIG
# ==========================================
TRAIN_WINDOW = 504
REBALANCE_FREQ = 63
COST_PER_TRADE = 0.0005
MAX_WEIGHT = 0.30
MIN_WEIGHT = 0.00
DELTA_MIN, DELTA_MAX = 0.5, 6.0
DELTA_SMOOTH = 0.7
VIEW_Z_CUTOFF_BASE = 0.35
TURNOVER_SKIP_THRESHOLD = 0.08
CONC_MAX_WEIGHT = 0.40
CONC_MOM_BONUS = 0.20
CONC_LEADER_Z_ON = 1.00
CONC_BREADTH_OFF = 0.40
MANUAL_EXTRA_CAP = 0.15
CONF_CAP_LO, CONF_CAP_HI = 0.05, 0.85


# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def download_prices(symbols, start_date):
    print(f"--- Downloading data for {len(symbols)} symbols starting {start_date} ---")
    try:
        bundle = yf.download(symbols, start=start_date, auto_adjust=False, progress=False)

        if isinstance(bundle.columns, pd.MultiIndex):
            if 'Adj Close' in bundle.columns.get_level_values(0):
                px = bundle['Adj Close']
            elif 'Close' in bundle.columns.get_level_values(0):
                px = bundle['Close']
            else:
                px = bundle
        else:
            if "Adj Close" in bundle:
                px = bundle["Adj Close"]
            elif "Close" in bundle:
                px = bundle["Close"]
            else:
                px = bundle

        px.index = pd.to_datetime(px.index)
        px = px.dropna(axis=1, how='all')

        print(f"--- Data Downloaded. Shape: {px.shape} ---")
        return px
    except Exception as e:
        print(f"!!! Error downloading data: {e}")
        return pd.DataFrame()


def risk_parity_anchor(cov: pd.DataFrame) -> pd.Series:
    vol = np.sqrt(np.diag(cov))
    w = 1.0 / (vol + 1e-12)
    w = w / w.sum()
    return pd.Series(w, index=cov.index)


def get_equilibrium_from_anchor(prices_train, market_prices_train, prev_delta=None):
    S = risk_models.CovarianceShrinkage(prices_train).ledoit_wolf()
    try:
        delta_raw = black_litterman.market_implied_risk_aversion(market_prices_train)
        if not np.isfinite(delta_raw): raise ValueError("delta not finite")
    except Exception:
        delta_raw = 2.5
    delta_raw = clamp(float(delta_raw), DELTA_MIN, DELTA_MAX)
    delta = delta_raw if prev_delta is None else (DELTA_SMOOTH * prev_delta + (1 - DELTA_SMOOTH) * delta_raw)
    w_anchor = risk_parity_anchor(S)
    pi = pd.Series(delta * (S @ w_anchor), index=prices_train.columns)
    return S, delta, pi, w_anchor


def detect_vol_regime(market_prices, current_date):
    mkt_hist = market_prices.loc[:current_date].dropna()
    if len(mkt_hist) < 100: return "low", np.nan, np.nan
    rolling_vol = mkt_hist.pct_change().rolling(63).std() * np.sqrt(252)
    hist_median = float(rolling_vol.median())
    tail = mkt_hist.iloc[-TRAIN_WINDOW:] if len(mkt_hist) >= TRAIN_WINDOW else mkt_hist
    realized_vol = float(tail.pct_change().std() * np.sqrt(252))
    regime = "high" if (
                np.isfinite(realized_vol) and np.isfinite(hist_median) and realized_vol > hist_median) else "low"
    return regime, realized_vol, hist_median


def detect_concentration_regime(prices_train: pd.DataFrame):
    if prices_train.shape[0] < 260: return False, None, np.nan, np.nan
    mom_12 = prices_train.pct_change(252).iloc[-1].dropna()
    if mom_12.empty: return False, None, np.nan, np.nan
    z_mom = (mom_12 - mom_12.mean()) / (mom_12.std() + 1e-12)
    leader = z_mom.idxmax()
    leader_z = float(z_mom.loc[leader])
    breadth = float((mom_12 > 0).mean())
    is_conc = (leader_z > CONC_LEADER_Z_ON) and (breadth < CONC_BREADTH_OFF)
    return bool(is_conc), str(leader), leader_z, breadth


def generate_dynamic_views(prices_train, pi, market_prices_train, vol_regime, mom_weight_override=None):
    spy_trend = market_prices_train.pct_change(252).iloc[-1]
    trend_strength = abs(spy_trend)
    mom_weight = 0.2 + 0.6 * (1 / (1 + np.exp(-10 * (trend_strength - 0.10))))
    rev_weight = 1.0 - mom_weight
    view_z_cutoff = VIEW_Z_CUTOFF_BASE
    if vol_regime == "high":
        view_z_cutoff = 0.45
        rev_weight = clamp(rev_weight + 0.20, 0.0, 1.0)
        mom_weight = 1.0 - rev_weight
    if mom_weight_override is not None:
        mom_weight = clamp(float(mom_weight_override), 0.0, 0.90)
        rev_weight = 1.0 - mom_weight

    raw_mom = prices_train.pct_change(252).iloc[-1].dropna()
    raw_rev = -prices_train.pct_change(21).iloc[-1].dropna()
    common = raw_mom.index.intersection(raw_rev.index).intersection(pi.index)
    raw_mom, raw_rev = raw_mom[common], raw_rev[common]
    z_mom = (raw_mom - raw_mom.mean()) / (raw_mom.std() + 1e-12)
    z_rev = (raw_rev - raw_rev.mean()) / (raw_rev.std() + 1e-12)
    combined_z = (mom_weight * z_mom) + (rev_weight * z_rev)
    asset_vol = prices_train[common].pct_change().std() * np.sqrt(252)

    view_dict = {}
    conf = {}
    for t in combined_z.index:
        z = float(combined_z[t])
        if abs(z) < view_z_cutoff: continue
        implied_ret = float(pi[t])
        vol = float(asset_vol[t])
        alpha = 0.35 * vol * z
        view_ret = implied_ret + alpha
        c = clamp(float(1 - np.exp(-abs(z))), 0.01, 0.99)
        view_dict[t] = float(view_ret)
        conf[t] = c
    return view_dict, pd.Series(conf), mom_weight, rev_weight, view_z_cutoff


def optimize_bl_portfolio(S, pi, view_dict, conf_series, delta, tickers, w_anchor, max_weight_active):
    if not view_dict: return w_anchor.reindex(tickers).fillna(0.0)
    conf_series = conf_series.reindex(list(view_dict.keys())).fillna(0.50)
    bl = black_litterman.BlackLittermanModel(S, pi=pi, absolute_views=view_dict, omega="idzorek",
                                             view_confidences=conf_series, risk_aversion=delta)
    ret_bl = bl.bl_returns()
    S_bl = bl.bl_cov()
    ef = EfficientFrontier(ret_bl, S_bl)
    ef.add_constraint(lambda w: w <= max_weight_active)
    ef.add_constraint(lambda w: w >= MIN_WEIGHT)
    ef.max_sharpe()
    return pd.Series(ef.clean_weights()).reindex(tickers).fillna(0.0)


def compute_leadership_features(prices_train: pd.DataFrame, market_train: pd.Series):
    if len(prices_train) < 260 or len(market_train) < 260: return None
    rs12 = (prices_train.iloc[-1] / prices_train.iloc[-252]) / (market_train.iloc[-1] / market_train.iloc[-252]) - 1
    rs6 = (prices_train.iloc[-1] / prices_train.iloc[-126]) / (market_train.iloc[-1] / market_train.iloc[-126]) - 1
    leadership_score = 0.7 * rs12 + 0.3 * rs6
    leader = leadership_score.idxmax()
    leader_strength = float(leadership_score.max())
    breadth = float((leadership_score > 0).mean())
    rets = prices_train.iloc[-126:].pct_change().dropna()
    disp = float(rets.std().mean() * np.sqrt(252))
    corr = rets.corr().values
    avg_corr = float(corr[np.triu_indices_from(corr, k=1)].mean())
    return {"leader": leader, "leader_strength": leader_strength, "breadth": breadth, "dispersion": disp,
            "avg_corr": avg_corr}


def build_ml_dataset(ml_rows):
    df = pd.DataFrame(ml_rows).dropna()
    if df.empty: return None, None, None
    feature_cols = ["leader_strength", "breadth", "dispersion", "avg_corr", "spy_trend_12m", "spy_vol_6m"]
    X = df[feature_cols].copy()
    y = df["label_momentum_works"].astype(int).copy()
    return X, y, feature_cols


def calc_max_drawdown(prices_series):
    roll_max = prices_series.cummax()
    drawdown = (prices_series - roll_max) / roll_max
    return float(drawdown.min())


# ==========================================
# ENGINE CLASS
# ==========================================
class BLEngine:
    def __init__(self, prices_df=None):
        self.tickers = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
        self.market_ticker = "SPY"
        self.risk_free_ticker = "^IRX"

        if prices_df is None:
            all_syms = self.tickers + [self.market_ticker, self.risk_free_ticker] + ["VNQ", "VOX"]
            prices_df = download_prices(all_syms, "2005-01-01")

        self.prices = prices_df
        if self.prices.empty:
            print("CRITICAL ERROR: No price data downloaded. Engine will fail.")
        else:
            self._prepare_data()

    def _prepare_data(self):
        if self.prices.index.tz is not None:
            self.prices.index = self.prices.index.tz_localize(None)

        if "VNQ" in self.prices.columns and "XLRE" in self.prices.columns:
            self.prices["XLRE"] = self.prices["XLRE"].fillna(self.prices["VNQ"])
        if "VOX" in self.prices.columns and "XLC" in self.prices.columns:
            self.prices["XLC"] = self.prices["XLC"].fillna(self.prices["VOX"])

        if self.market_ticker in self.prices.columns:
            self.market_prices = self.prices[self.market_ticker].dropna()
        else:
            self.market_prices = pd.Series()

        if self.risk_free_ticker in self.prices.columns:
            self.rf_prices = self.prices[self.risk_free_ticker].ffill()
            self.rf_daily = (self.rf_prices / 100.0) / 252.0
        else:
            self.rf_daily = pd.Series(0.04 / 252, index=self.prices.index)

        available_tickers = [t for t in self.tickers if t in self.prices.columns]
        self.asset_prices = self.prices[available_tickers].dropna(how="any")

        common = self.asset_prices.index.intersection(self.market_prices.index).intersection(self.rf_daily.index)

        if len(common) == 0:
            print("CRITICAL: No common dates found. Check Timezones or Ticker Data.")
            common = self.asset_prices.index.intersection(self.market_prices.index)
            self.rf_daily = self.rf_daily.reindex(common).fillna(0.04 / 252)

        self.asset_prices = self.asset_prices.loc[common]
        self.market_prices = self.market_prices.loc[common]
        self.rf_daily = self.rf_daily.loc[common]

        print(f"--- Data Prepared. Rows: {len(self.asset_prices)} ---")

    def _get_data_window(self, target_date=None):
        if not target_date: return self.asset_prices, self.market_prices
        dt = pd.Timestamp(target_date)
        return self.asset_prices.loc[:dt], self.market_prices.loc[:dt]

    def run_scenario(self, user_views: list, target_date: str = None):
        assets_hist, mkt_hist = self._get_data_window(target_date)
        if len(assets_hist) < 504: return {"error": f"Not enough data for {target_date}"}

        train_window = 504
        train_prices = assets_hist.iloc[-train_window:]
        train_mkt = mkt_hist.iloc[-train_window:]
        current_date = train_prices.index[-1]

        vol_regime, _, _ = detect_vol_regime(mkt_hist, current_date)
        S, delta, pi, w_anchor = get_equilibrium_from_anchor(train_prices, train_mkt)
        view_dict, conf_series, _, _, _ = generate_dynamic_views(train_prices, pi, train_mkt, vol_regime)

        applied = []
        for v in user_views:
            t = v['ticker']
            if t in self.tickers:
                view_dict[t] = pi[t] + float(v['value'])
                conf_series[t] = float(v['confidence'])
                applied.append(f"{t} +{v['value']:.1%}")

        weights = optimize_bl_portfolio(S, pi, view_dict, conf_series, delta, self.tickers, w_anchor, 0.40)

        port_ret = float(weights.dot(pi))
        port_var = weights.T @ S @ weights
        port_vol = float(np.sqrt(port_var))

        return {
            "date": str(current_date.date()),
            "weights": weights.to_dict(),
            "regime": {"volatility": vol_regime},
            "metrics": {"delta": round(delta, 2), "expected_return": port_ret, "volatility": port_vol},
            "applied_scenarios": applied
        }

    def run_monte_carlo(self, mu, sigma, days=252, n_sims=5000):
        dt = 1 / 252
        paths = np.zeros((days, n_sims))
        paths[0] = 100
        for t in range(1, days):
            z = np.random.standard_normal(n_sims)
            paths[t] = paths[t - 1] * np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z)

        random_indices = np.random.choice(n_sims, 5, replace=False)
        sample_paths = paths[:, random_indices].T.tolist()

        return {
            "days": list(range(days)),
            "p05": np.percentile(paths, 5, axis=1).tolist(),
            "p25": np.percentile(paths, 25, axis=1).tolist(),
            "p50": np.percentile(paths, 50, axis=1).tolist(),
            "p75": np.percentile(paths, 75, axis=1).tolist(),
            "p95": np.percentile(paths, 95, axis=1).tolist(),
            "sample_paths": sample_paths,
            "simulation_count": n_sims
        }

    def run_backtest(self, start_date: str, end_date: str, user_views: list, initial_capital=10000.0):
        full_slice = self.asset_prices
        try:
            req_start_idx = full_slice.index.get_indexer([pd.Timestamp(start_date)], method='nearest')[0]
        except:
            return {"error": "Invalid start date"}

        start_idx = TRAIN_WINDOW
        while start_idx < req_start_idx:
            start_idx += REBALANCE_FREQ
        if start_idx < TRAIN_WINDOW: start_idx = TRAIN_WINDOW

        ml_rows = []
        ml_model = None
        ml_available = True

        portfolio_returns_history = []
        spy_returns_history = []
        
        # --- FIXED: Use a simple list of tuples to store (Date, Weights) ---
        weights_snapshots = [] 

        prev_weights = pd.Series(0.0, index=self.tickers)
        prev_delta = None

        for i in range(start_idx, len(full_slice), REBALANCE_FREQ):
            train_prices = full_slice.iloc[i - TRAIN_WINDOW:i]
            train_mkt = self.market_prices.loc[train_prices.index]

            test_end = min(i + REBALANCE_FREQ, len(full_slice))
            if full_slice.index[i] > pd.Timestamp(end_date): break

            test_prices = full_slice.iloc[i:test_end]
            test_mkt = self.market_prices.loc[test_prices.index]

            if test_prices.shape[0] < 2: break

            current_date = train_prices.index[-1]

            vol_regime, _, _ = detect_vol_regime(self.market_prices, current_date)
            S, delta, pi, w_anchor = get_equilibrium_from_anchor(train_prices, train_mkt, prev_delta)
            prev_delta = delta

            leader_info = compute_leadership_features(train_prices, train_mkt)

            mom_weight_override = None
            spy_trend_12m = np.nan
            spy_vol_6m = np.nan

            if len(train_mkt) >= 260:
                spy_trend_12m = float(train_mkt.pct_change(252).iloc[-1])
            if len(train_mkt) >= 140:
                spy_vol_6m = float(train_mkt.iloc[-126:].pct_change().std() * np.sqrt(252))

            if ml_available:
                X_train, y_train, fcols = build_ml_dataset(ml_rows)
                if X_train is not None and len(X_train) >= 30 and y_train.nunique() > 1 and leader_info:
                    ml_model = Pipeline([("s", StandardScaler()), ("c", LogisticRegression(max_iter=2000))])
                    ml_model.fit(X_train, y_train)
                    X_now = pd.DataFrame([{
                        "leader_strength": leader_info["leader_strength"],
                        "breadth": leader_info["breadth"],
                        "dispersion": leader_info["dispersion"],
                        "avg_corr": leader_info["avg_corr"],
                        "spy_trend_12m": spy_trend_12m,
                        "spy_vol_6m": spy_vol_6m,
                    }])[fcols]
                    p_mom = float(ml_model.predict_proba(X_now)[0, 1])
                    mom_weight_override = clamp(0.25 + 0.60 * p_mom, 0.25, 0.85)

            is_conc, _, _, _ = detect_concentration_regime(train_prices)
            max_w = 0.40 if is_conc else 0.30
            if is_conc and mom_weight_override: mom_weight_override = clamp(mom_weight_override + CONC_MOM_BONUS, 0.25, 0.90)

            view_dict, conf_series, _, _, _ = generate_dynamic_views(train_prices, pi, train_mkt, vol_regime, mom_weight_override)

            for v in user_views:
                t = v['ticker']
                if t in self.tickers:
                    extra = float(clamp(v['value'], -MANUAL_EXTRA_CAP, MANUAL_EXTRA_CAP))
                    conf = float(clamp(v['confidence'], CONF_CAP_LO, CONF_CAP_HI))
                    view_dict[t] = float(pi[t]) + extra
                    conf_series[t] = conf

            weights = optimize_bl_portfolio(S, pi, view_dict, conf_series, delta, self.tickers, w_anchor, max_w)

            w_aligned = weights.reindex(self.tickers).fillna(0.0)
            
            # --- FIXED: Store tuple of (Date, Weights) ---
            weights_active_date = test_prices.index[0]
            weights_snapshots.append((weights_active_date, w_aligned))
            # ---------------------------------------------

            prev_aligned = prev_weights.reindex(self.tickers).fillna(0.0)
            turnover = np.abs(w_aligned - prev_aligned).sum() / 2.0

            skipped = False
            if turnover < TURNOVER_SKIP_THRESHOLD:
                w_aligned = prev_aligned
                turnover = 0.0
                skipped = True
            else:
                prev_weights = w_aligned

            period_rel = test_prices.div(test_prices.iloc[0])
            period_val = period_rel.dot(w_aligned)
            period_ret = period_val.pct_change().dropna()

            if not period_ret.empty and not skipped:
                period_ret.iloc[0] -= (turnover * COST_PER_TRADE)

            portfolio_returns_history.append(period_ret)
            spy_rel = test_mkt.div(test_mkt.iloc[0])
            spy_ret = spy_rel.pct_change().dropna()
            spy_returns_history.append(spy_ret)

        if not portfolio_returns_history: return {"error": "No simulation data generated"}

        full_port_rets = pd.concat(portfolio_returns_history)
        full_spy_rets = pd.concat(spy_returns_history)

        # --- REBUILT WEIGHT CALCULATION ---
        # 1. Unpack tuples
        if weights_snapshots:
            dates, w_list = zip(*weights_snapshots)
            df_w = pd.DataFrame(w_list, index=dates)
            df_w.index = pd.to_datetime(df_w.index)
            # 2. Expand to daily frequency (matching returns index)
            df_w_daily = df_w.reindex(full_port_rets.index, method='ffill')
        else:
            df_w_daily = pd.DataFrame()

        port_curve = (1 + full_port_rets).cumprod() * initial_capital
        spy_curve = (1 + full_spy_rets).cumprod() * initial_capital

        df_res = pd.DataFrame({'Portfolio': port_curve, 'SPY': spy_curve})
        yearly_res = df_res.resample('Y').last().pct_change().dropna()
        
        yearly_table = []
        for dt, row in yearly_res.iterrows():
            holdings_str = ""
            if not df_w_daily.empty:
                # Filter for this specific year
                # We use the daily DataFrame, so we get the average actual exposure during that year
                mask = df_w_daily.index.year == dt.year
                if mask.any():
                    avg_w = df_w_daily.loc[mask].mean()
                    top_3 = avg_w.sort_values(ascending=False).head(3)
                    holdings_str = " ".join([f"{t}({w:.0%})" for t, w in top_3.items() if w > 0.01])

            if not holdings_str: holdings_str = "Cash/Div."

            yearly_table.append({
                "year": dt.year,
                "portfolio": row['Portfolio'],
                "spy": row['SPY'],
                "diff": row['Portfolio'] - row['SPY'],
                "top_holdings": holdings_str
            })

        rets = df_res.pct_change().dropna()
        sharpe_port = (rets['Portfolio'].mean() * 252) / (rets['Portfolio'].std() * np.sqrt(252))
        sharpe_spy = (rets['SPY'].mean() * 252) / (rets['SPY'].std() * np.sqrt(252))
        dd_port = calc_max_drawdown(df_res['Portfolio'])
        dd_spy = calc_max_drawdown(df_res['SPY'])
        vol_port = rets['Portfolio'].std() * np.sqrt(252)
        vol_spy = rets['SPY'].std() * np.sqrt(252)

        return {
            "dates": [str(d.date()) for d in df_res.index],
            "portfolio": df_res['Portfolio'].tolist(),
            "spy": df_res['SPY'].tolist(),
            "metrics": {
                "total_return": (port_curve.iloc[-1] / initial_capital) - 1,
                "spy_total_return": (spy_curve.iloc[-1] / initial_capital) - 1,
                "sharpe": sharpe_port if np.isfinite(sharpe_port) else 0.0,
                "spy_sharpe": sharpe_spy if np.isfinite(sharpe_spy) else 0.0,
                "max_dd": dd_port,
                "spy_max_dd": dd_spy,
                "volatility": vol_port,
                "spy_volatility": vol_spy
            },
            "yearly_table": yearly_table
        }
