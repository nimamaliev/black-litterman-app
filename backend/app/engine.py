import pandas as pd
import numpy as np
import yfinance as yf
from pypfopt import black_litterman, risk_models, EfficientFrontier
import warnings
import logging
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

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
DEFAULT_RF = 0.02  # fallback annual risk-free rate when ^IRX is unavailable

# --- Defensive volatility-targeting overlay -------------------------------
# When VOL_TARGET is not None (annualized, e.g. 0.10 = 10%), daily portfolio
# exposure in run_backtest is scaled so trailing realized volatility ~ VOL_TARGET;
# the un-invested fraction earns the daily risk-free rate. No leverage or
# shorting (exposure clamped to [EXPOSURE_FLOOR, EXPOSURE_CAP]); the signal is
# lagged one day to avoid look-ahead. Set VOL_TARGET = None to disable and
# recover the original always-invested behavior.
VOL_TARGET = 0.10
VOL_TARGET_LOOKBACK = 21
EXPOSURE_FLOOR = 0.00
EXPOSURE_CAP = 1.00


# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def download_prices(symbols, start_date):
    """Download a flattened price DataFrame for the given symbols.

    Delegates to data_loader.download_and_flatten so the Yahoo Finance
    download + column-flattening logic lives in exactly one place.
    """
    from app.data_loader import download_and_flatten
    try:
        return download_and_flatten(symbols, start_date)
    except Exception as e:
        logger.error("Error downloading data: %s", e)
        return pd.DataFrame()


def inverse_vol_anchor(cov: pd.DataFrame) -> pd.Series:
    """Inverse-volatility weights used as the equilibrium anchor.

    NOTE: This is a simplified risk-based anchor (weights proportional to 1/vol).
    It is NOT full risk parity / equal risk contribution (ERC), which would
    account for cross-asset correlations via the full covariance matrix.
    """
    vol = np.sqrt(np.diag(cov))
    w = 1.0 / (vol + 1e-12)
    w = w / w.sum()
    return pd.Series(w, index=cov.index)


def get_equilibrium_from_anchor(prices_train, market_prices_train, prev_delta=None):
    S = risk_models.CovarianceShrinkage(prices_train).ledoit_wolf()
    try:
        delta_raw = black_litterman.market_implied_risk_aversion(market_prices_train)
        if not np.isfinite(delta_raw):
            raise ValueError("delta not finite")
    except Exception:
        delta_raw = 2.5
    delta_raw = clamp(float(delta_raw), DELTA_MIN, DELTA_MAX)
    delta = delta_raw if prev_delta is None else (DELTA_SMOOTH * prev_delta + (1 - DELTA_SMOOTH) * delta_raw)
    w_anchor = inverse_vol_anchor(S)
    pi = pd.Series(delta * (S @ w_anchor), index=prices_train.columns)
    return S, delta, pi, w_anchor


def detect_vol_regime(market_prices, current_date):
    mkt_hist = market_prices.loc[:current_date].dropna()
    if len(mkt_hist) < 100:
        return "low", np.nan, np.nan
    rolling_vol = mkt_hist.pct_change().rolling(63).std() * np.sqrt(252)
    hist_median = float(rolling_vol.median())
    tail = mkt_hist.iloc[-TRAIN_WINDOW:] if len(mkt_hist) >= TRAIN_WINDOW else mkt_hist
    realized_vol = float(tail.pct_change().std() * np.sqrt(252))
    regime = "high" if (
                np.isfinite(realized_vol) and np.isfinite(hist_median) and realized_vol > hist_median) else "low"
    return regime, realized_vol, hist_median


def detect_concentration_regime(prices_train: pd.DataFrame):
    if prices_train.shape[0] < 260:
        return False, None, np.nan, np.nan
    mom_12 = prices_train.pct_change(252).iloc[-1].dropna()
    if mom_12.empty:
        return False, None, np.nan, np.nan
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
        if abs(z) < view_z_cutoff:
            continue
        implied_ret = float(pi[t])
        vol = float(asset_vol[t])
        alpha = 0.35 * vol * z
        view_ret = implied_ret + alpha
        c = clamp(float(1 - np.exp(-abs(z))), 0.01, 0.99)
        view_dict[t] = float(view_ret)
        conf[t] = c
    return view_dict, pd.Series(conf), mom_weight, rev_weight, view_z_cutoff


def optimize_bl_portfolio(S, pi, view_dict, conf_series, delta, tickers, w_anchor,
                          max_weight_active, risk_free_rate=DEFAULT_RF):
    """Returns (weights, posterior_returns, posterior_cov).

    When there are no views, the anchor weights are returned and the posterior
    collapses to the prior (pi, S).
    """
    if not view_dict:
        w = w_anchor.reindex(tickers).fillna(0.0)
        return w, pi.copy(), S
    conf_series = conf_series.reindex(list(view_dict.keys())).fillna(0.50)
    bl = black_litterman.BlackLittermanModel(S, pi=pi, absolute_views=view_dict, omega="idzorek",
                                             view_confidences=conf_series, risk_aversion=delta)
    ret_bl = bl.bl_returns()
    S_bl = bl.bl_cov()
    ef = EfficientFrontier(ret_bl, S_bl)
    ef.add_constraint(lambda w: w <= max_weight_active)
    ef.add_constraint(lambda w: w >= MIN_WEIGHT)
    # Pass an explicit risk-free rate so the optimizer and our reported metrics agree.
    ef.max_sharpe(risk_free_rate=risk_free_rate)
    weights = pd.Series(ef.clean_weights()).reindex(tickers).fillna(0.0)
    return weights, ret_bl, S_bl


def compute_leadership_features(prices_train: pd.DataFrame, market_train: pd.Series):
    if len(prices_train) < 260 or len(market_train) < 260:
        return None
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
    if df.empty:
        return None, None, None
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
            logger.error("CRITICAL ERROR: No price data downloaded. Engine will fail.")
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
            self.rf_daily = pd.Series(DEFAULT_RF / 252, index=self.prices.index)

        available_tickers = [t for t in self.tickers if t in self.prices.columns]
        self.asset_prices = self.prices[available_tickers].dropna(how="any")

        common = self.asset_prices.index.intersection(self.market_prices.index).intersection(self.rf_daily.index)

        if len(common) == 0:
            logger.error("CRITICAL: No common dates found. Check Timezones or Ticker Data.")
            common = self.asset_prices.index.intersection(self.market_prices.index)
            self.rf_daily = self.rf_daily.reindex(common).fillna(DEFAULT_RF / 252)

        self.asset_prices = self.asset_prices.loc[common]
        self.market_prices = self.market_prices.loc[common]
        self.rf_daily = self.rf_daily.loc[common]

        logger.info("Data prepared. Rows: %d", len(self.asset_prices))

    def _annual_rf(self, as_of_date=None):
        """Most recent annualized risk-free rate at/just before as_of_date."""
        try:
            series = self.rf_daily if as_of_date is None else self.rf_daily.loc[:as_of_date]
            series = series.dropna()
            if series.empty:
                return DEFAULT_RF
            return float(series.iloc[-1] * 252)
        except Exception:
            return DEFAULT_RF

    def _get_data_window(self, target_date=None):
        if not target_date:
            return self.asset_prices, self.market_prices
        dt = pd.Timestamp(target_date)
        return self.asset_prices.loc[:dt], self.market_prices.loc[:dt]

    def run_scenario(self, user_views: list, target_date: str = None):
        assets_hist, mkt_hist = self._get_data_window(target_date)
        if len(assets_hist) < 504:
            return {"error": f"Not enough data for {target_date}"}

        train_window = 504
        train_prices = assets_hist.iloc[-train_window:]
        train_mkt = mkt_hist.iloc[-train_window:]
        current_date = train_prices.index[-1]

        rf_now = self._annual_rf(current_date)

        vol_regime, _, _ = detect_vol_regime(mkt_hist, current_date)
        S, delta, pi, w_anchor = get_equilibrium_from_anchor(train_prices, train_mkt)
        view_dict, conf_series, _, _, _ = generate_dynamic_views(train_prices, pi, train_mkt, vol_regime)

        # Apply user views with the SAME clamping rules used in the backtest,
        # so the dashboard and backtest treat discretionary views identically.
        applied = []
        input_warnings = []
        for v in user_views:
            t = v['ticker']
            if t not in self.tickers:
                input_warnings.append(
                    f"Ignored unknown ticker '{t}'. Valid tickers: {', '.join(self.tickers)}."
                )
                continue
            raw_val = float(v['value'])
            raw_conf = float(v['confidence'])
            extra = float(clamp(raw_val, -MANUAL_EXTRA_CAP, MANUAL_EXTRA_CAP))
            conf = float(clamp(raw_conf, CONF_CAP_LO, CONF_CAP_HI))
            if extra != raw_val:
                input_warnings.append(
                    f"{t}: excess return {raw_val:.1%} was capped to {extra:.1%} "
                    f"(allowed range \u00b1{MANUAL_EXTRA_CAP:.0%})."
                )
            if conf != raw_conf:
                input_warnings.append(
                    f"{t}: confidence {raw_conf:.0%} was capped to {conf:.0%} "
                    f"(allowed range {CONF_CAP_LO:.0%}-{CONF_CAP_HI:.0%})."
                )
            view_dict[t] = float(pi[t]) + extra
            conf_series[t] = conf
            applied.append(f"{t} +{extra:.1%}")

        weights, ret_post, S_post = optimize_bl_portfolio(
            S, pi, view_dict, conf_series, delta, self.tickers, w_anchor, 0.40, risk_free_rate=rf_now
        )

        # Report expected return/vol against the BL POSTERIOR (the distribution
        # the portfolio was actually optimized on), not the prior pi.
        common_t = [t for t in self.tickers if t in S_post.index]
        w_vec = weights.reindex(common_t).fillna(0.0)
        ret_vec = ret_post.reindex(common_t).fillna(0.0)
        S_mat = S_post.reindex(index=common_t, columns=common_t)
        port_ret = float(w_vec.values @ ret_vec.values)
        port_var = float(w_vec.values @ S_mat.values @ w_vec.values)
        port_vol = float(np.sqrt(max(port_var, 0.0)))

        # Prior (market-implied equilibrium) vs posterior (after views) expected
        # returns per sector, so the UI can visualize how the views moved them.
        expected_returns = {
            "prior": {t: float(pi.get(t, 0.0)) for t in self.tickers},
            "posterior": {t: float(ret_post.get(t, 0.0)) for t in self.tickers},
        }

        # Plain-language summary for non-technical users.
        sharpe_val = (port_ret - rf_now) / port_vol if port_vol > 1e-9 else 0.0
        ranked = sorted(weights.to_dict().items(), key=lambda kv: kv[1], reverse=True)
        top = [(t, w) for t, w in ranked if w > 0.005][:3]
        holdings_txt = (
            ", ".join(f"{t} ({w:.0%})" for t, w in top) if top else "a broadly balanced mix"
        )
        summary = (
            f"As of {current_date.date()}, the model's largest positions are {holdings_txt}. "
            f"It targets an expected annual return of {port_ret:.1%} with {port_vol:.1%} "
            f"volatility (Sharpe {sharpe_val:.2f}), in a {vol_regime}-volatility market regime."
        )
        if applied:
            plural = "s" if len(applied) != 1 else ""
            summary += (
                f" Your {len(applied)} view{plural} ({', '.join(applied)}) have been incorporated."
            )

        # --- Live volatility-target exposure (mirrors the backtest overlay) ---
        # Estimate trailing realized portfolio volatility from the recommended
        # weights over the last VOL_TARGET_LOOKBACK days, then scale exposure
        # toward VOL_TARGET. Whatever is not invested sits in cash at the rf rate.
        exposure = 1.0
        realized_vol = None
        if VOL_TARGET is not None:
            recent_rets = train_prices.pct_change().iloc[-VOL_TARGET_LOOKBACK:]
            w_live = weights.reindex(recent_rets.columns).fillna(0.0)
            port_rets_live = recent_rets.values @ w_live.values
            realized_vol = float(np.nanstd(port_rets_live, ddof=1) * np.sqrt(252))
            if realized_vol > 1e-9:
                exposure = float(np.clip(VOL_TARGET / realized_vol, EXPOSURE_FLOOR, EXPOSURE_CAP))
        invested_pct = exposure
        cash_pct = 1.0 - exposure

        summary += (
            f" Given current volatility, the model recommends being about "
            f"{invested_pct:.0%} invested and {cash_pct:.0%} in cash."
        )

        return {
            "date": str(current_date.date()),
            "exposure": {
                "invested": invested_pct,
                "cash": cash_pct,
                "vol_target": VOL_TARGET,
                "realized_vol": realized_vol,
            },
            "weights": weights.to_dict(),
            "regime": {"volatility": vol_regime},
            "metrics": {
                "delta": round(delta, 2),
                "expected_return": port_ret,
                "volatility": port_vol,
                "risk_free": rf_now,
            },
            "expected_returns": expected_returns,
            "summary": summary,
            "warnings": input_warnings,
            "applied_scenarios": applied
        }

    def run_monte_carlo(self, mu, sigma, days=252, n_sims=5000, n_samples=3, seed=42):
        # Seeded RNG for reproducible projections.
        rng = np.random.default_rng(seed)
        dt = 1 / 252
        paths = np.zeros((days, n_sims))
        paths[0] = 100
        for t in range(1, days):
            z = rng.standard_normal(n_sims)
            paths[t] = paths[t - 1] * np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z)

        # Sample exactly the number of spaghetti paths the UI renders.
        n_samples = int(min(n_samples, n_sims))
        random_indices = rng.choice(n_sims, n_samples, replace=False)
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
            ts_start = pd.Timestamp(start_date)
            ts_end = pd.Timestamp(end_date)
        except Exception:
            return {"error": "Invalid date format. Please use YYYY-MM-DD."}
        if ts_start >= ts_end:
            return {"error": "Start date must be before end date."}
        try:
            req_start_idx = full_slice.index.get_indexer([ts_start], method='nearest')[0]
        except Exception:
            return {"error": "Invalid start date"}

        start_idx = TRAIN_WINDOW
        while start_idx < req_start_idx:
            start_idx += REBALANCE_FREQ
        if start_idx < TRAIN_WINDOW:
            start_idx = TRAIN_WINDOW

        # Validate user views once up front and collect human-readable warnings
        # (instead of silently clamping out-of-range inputs inside the loop).
        input_warnings = []
        valid_tickers = set(self.tickers)
        for v in user_views:
            t = v.get('ticker')
            if t not in valid_tickers:
                input_warnings.append(
                    f"Ignored unknown ticker '{t}'. Valid tickers: {', '.join(self.tickers)}."
                )
                continue
            raw_val = float(v['value'])
            raw_conf = float(v['confidence'])
            if clamp(raw_val, -MANUAL_EXTRA_CAP, MANUAL_EXTRA_CAP) != raw_val:
                input_warnings.append(
                    f"{t}: excess return {raw_val:.1%} will be capped to "
                    f"\u00b1{MANUAL_EXTRA_CAP:.0%}."
                )
            if clamp(raw_conf, CONF_CAP_LO, CONF_CAP_HI) != raw_conf:
                input_warnings.append(
                    f"{t}: confidence {raw_conf:.0%} will be capped to "
                    f"{CONF_CAP_LO:.0%}-{CONF_CAP_HI:.0%}."
                )
            sd = v.get('start_date')
            ed = v.get('end_date')
            if sd and ed:
                try:
                    if pd.Timestamp(sd) > pd.Timestamp(ed):
                        input_warnings.append(
                            f"{t}: view start date is after its end date; "
                            f"this view may never apply."
                        )
                except Exception:
                    input_warnings.append(f"{t}: could not parse the view's date range.")

        ml_rows = []
        ml_model = None
        ml_available = True

        portfolio_returns_history = []
        spy_returns_history = []

        # --- Store tuple of (Date, Weights) ---
        weights_snapshots = []

        prev_weights = pd.Series(0.0, index=self.tickers)
        prev_delta = None

        for i in range(start_idx, len(full_slice), REBALANCE_FREQ):
            train_prices = full_slice.iloc[i - TRAIN_WINDOW:i]
            train_mkt = self.market_prices.loc[train_prices.index]

            test_end = min(i + REBALANCE_FREQ, len(full_slice))
            if full_slice.index[i] > pd.Timestamp(end_date):
                break

            test_prices = full_slice.iloc[i:test_end]
            test_mkt = self.market_prices.loc[test_prices.index]

            if test_prices.shape[0] < 2:
                break

            current_date = train_prices.index[-1]
            period_date = test_prices.index[0]
            rf_now = self._annual_rf(current_date)

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

                    logger.info("AI ACTIVE | Date: %s | Training Data: %d rows | Prediction: Momentum has %.1f%% chance of working", current_date.date(), len(X_train), p_mom * 100)

            is_conc, _, _, _ = detect_concentration_regime(train_prices)
            max_w = CONC_MAX_WEIGHT if is_conc else MAX_WEIGHT
            if is_conc and mom_weight_override:
                mom_weight_override = clamp(mom_weight_override + CONC_MOM_BONUS, 0.25, 0.90)

            view_dict, conf_series, _, _, _ = generate_dynamic_views(train_prices, pi, train_mkt, vol_regime, mom_weight_override)

            # Apply user views, honoring each view's optional [start_date, end_date]
            # window so the per-view date controls in the UI actually take effect.
            for v in user_views:
                t = v['ticker']
                if t not in self.tickers:
                    continue
                sd = v.get('start_date')
                ed = v.get('end_date')
                if sd and period_date < pd.Timestamp(sd):
                    continue
                if ed and period_date > pd.Timestamp(ed):
                    continue
                extra = float(clamp(v['value'], -MANUAL_EXTRA_CAP, MANUAL_EXTRA_CAP))
                conf = float(clamp(v['confidence'], CONF_CAP_LO, CONF_CAP_HI))
                view_dict[t] = float(pi[t]) + extra
                conf_series[t] = conf

            weights, _, _ = optimize_bl_portfolio(
                S, pi, view_dict, conf_series, delta, self.tickers, w_anchor, max_w, risk_free_rate=rf_now
            )

            w_aligned = weights.reindex(self.tickers).fillna(0.0)

            prev_aligned = prev_weights.reindex(self.tickers).fillna(0.0)
            turnover = np.abs(w_aligned - prev_aligned).sum() / 2.0

            skipped = False
            if turnover < TURNOVER_SKIP_THRESHOLD:
                w_aligned = prev_aligned
                turnover = 0.0
                skipped = True
            else:
                prev_weights = w_aligned

            # --- Store the weights ACTUALLY held this period (after the skip
            # decision), so the "Top Holdings" report matches reality. ---
            weights_snapshots.append((period_date, w_aligned))

            period_rel = test_prices.div(test_prices.iloc[0])
            period_val = period_rel.dot(w_aligned)
            period_ret = period_val.pct_change().dropna()

            if not period_ret.empty and not skipped:
                period_ret.iloc[0] -= (turnover * COST_PER_TRADE)

            portfolio_returns_history.append(period_ret)
            spy_rel = test_mkt.div(test_mkt.iloc[0])
            spy_ret = spy_rel.pct_change().dropna()
            spy_returns_history.append(spy_ret)

            # --- ML LABEL GENERATION ---
            if ml_available and not test_mkt.empty and leader_info:
                future_mkt_ret = (test_mkt.iloc[-1] / test_mkt.iloc[0]) - 1
                label = 1 if future_mkt_ret > 0 else 0
                ml_rows.append({
                    "leader_strength": leader_info["leader_strength"],
                    "breadth": leader_info["breadth"],
                    "dispersion": leader_info["dispersion"],
                    "avg_corr": leader_info["avg_corr"],
                    "spy_trend_12m": spy_trend_12m if np.isfinite(spy_trend_12m) else 0.0,
                    "spy_vol_6m": spy_vol_6m if np.isfinite(spy_vol_6m) else 0.0,
                    "label_momentum_works": label
                })

        if not portfolio_returns_history:
            return {"error": "No simulation data generated"}

        full_port_rets = pd.concat(portfolio_returns_history)
        full_spy_rets = pd.concat(spy_returns_history)

        # --- Defensive volatility-targeting overlay (optional) ---
        # Scale daily exposure so trailing realized vol ~ VOL_TARGET, parking the
        # rest at the risk-free rate. Lagged one day (no look-ahead). This is the
        # validated crash-defense overlay; set VOL_TARGET = None above to disable.
        if VOL_TARGET is not None:
            realized_vol = full_port_rets.rolling(VOL_TARGET_LOOKBACK).std() * np.sqrt(252)
            exposure = (VOL_TARGET / realized_vol).shift(1).clip(EXPOSURE_FLOOR, EXPOSURE_CAP).fillna(EXPOSURE_CAP)
            rf_overlay = self.rf_daily.reindex(full_port_rets.index).fillna(0.0)
            full_port_rets = exposure * full_port_rets + (1 - exposure) * rf_overlay

        port_curve = (1 + full_port_rets).cumprod() * initial_capital
        spy_curve = (1 + full_spy_rets).cumprod() * initial_capital

        df_res = pd.DataFrame({'Portfolio': port_curve, 'SPY': spy_curve})
        # 'YE' (year-end) replaces deprecated 'Y' alias in pandas >= 2.2.
        year_end_vals = df_res.resample('YE').last()
        # Prepend the starting capital (dated just before inception) so the
        # first partial year is measured from inception instead of being
        # silently dropped by pct_change().
        start_row = pd.DataFrame(
            {'Portfolio': initial_capital, 'SPY': initial_capital},
            index=[df_res.index[0] - pd.Timedelta(days=1)],
        )
        yearly_res = pd.concat([start_row, year_end_vals]).pct_change().dropna()

        yearly_table = []

        # --- FAILSAFE WEIGHT MATCHING LOGIC ---
        for dt, row in yearly_res.iterrows():
            year_int = dt.year

            # 1. Collect all weight snapshots that happened during this year
            weights_in_year = []
            for (w_date, w_series) in weights_snapshots:
                if w_date.year == year_int:
                    weights_in_year.append(w_series)

            # Default text
            holdings_str = "Balanced"

            # 2. If we found any weights for this year, average them and format
            if weights_in_year:
                avg_weights = pd.DataFrame(weights_in_year).mean()
                top_3 = avg_weights.sort_values(ascending=False).head(3)
                parts = [f"{t}({w:.0%})" for t, w in top_3.items() if w > 0.01]
                if parts:
                    holdings_str = " ".join(parts)

            yearly_table.append({
                "year": year_int,
                "portfolio": row['Portfolio'],
                "spy": row['SPY'],
                "diff": row['Portfolio'] - row['SPY'],
                "top_holdings": holdings_str
            })
        # --------------------------------------

        rets = df_res.pct_change().dropna()
        # Excess (risk-free-adjusted) Sharpe, using the average ^IRX yield over the window.
        rf_window = self.rf_daily.reindex(df_res.index).ffill().dropna()
        rf_ann = float(rf_window.mean() * 252) if not rf_window.empty else DEFAULT_RF

        def _sharpe(col):
            ann_ret = rets[col].mean() * 252
            ann_vol = rets[col].std() * np.sqrt(252)
            if not np.isfinite(ann_vol) or ann_vol == 0:
                return 0.0
            val = (ann_ret - rf_ann) / ann_vol
            return float(val) if np.isfinite(val) else 0.0

        sharpe_port = _sharpe('Portfolio')
        sharpe_spy = _sharpe('SPY')
        dd_port = calc_max_drawdown(df_res['Portfolio'])
        dd_spy = calc_max_drawdown(df_res['SPY'])
        vol_port = rets['Portfolio'].std() * np.sqrt(252)
        vol_spy = rets['SPY'].std() * np.sqrt(252)

        total_return = (port_curve.iloc[-1] / initial_capital) - 1
        spy_total_return = (spy_curve.iloc[-1] / initial_capital) - 1
        verb = "outperformed" if total_return >= spy_total_return else "underperformed"
        summary = (
            f"From {df_res.index[0].date()} to {df_res.index[-1].date()}, the strategy "
            f"returned {total_return:.1%} versus {spy_total_return:.1%} for SPY - it {verb} "
            f"the benchmark by {abs(total_return - spy_total_return):.1%}. Risk-adjusted, its "
            f"Sharpe was {sharpe_port:.2f} (SPY {sharpe_spy:.2f}) with a max drawdown of "
            f"{dd_port:.1%} (SPY {dd_spy:.1%})."
        )

        return {
            "dates": [str(d.date()) for d in df_res.index],
            "portfolio": df_res['Portfolio'].tolist(),
            "spy": df_res['SPY'].tolist(),
            "metrics": {
                "total_return": total_return,
                "spy_total_return": spy_total_return,
                "sharpe": sharpe_port,
                "spy_sharpe": sharpe_spy,
                "max_dd": dd_port,
                "spy_max_dd": dd_spy,
                "volatility": vol_port,
                "spy_volatility": vol_spy,
                "risk_free": rf_ann
            },
            "yearly_table": yearly_table,
            "summary": summary,
            "warnings": input_warnings
        }
