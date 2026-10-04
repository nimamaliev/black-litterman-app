"""Black-Litterman sector allocation engine (Defensive model).

Pipeline at every rebalance date, using only data available on that date:

1. Prior (equilibrium). The market portfolio is SPY. Its sector weights are
   recovered by returns-based style analysis (non-negative weights summing to 1
   that best replicate SPY's trailing daily returns), which approximates the
   cap weights of the 11 SPDR sector ETFs without needing market-cap data.
   Reverse optimisation gives the implied excess returns
   pi = delta * Sigma * w_mkt, with delta = MARKET_ERP / market variance.

2. Views. One relative view per signal in VIEW_SIGNALS: "the top-k sectors by
   this score will outperform the bottom-k". P is the long/short view portfolio
   and Q = P.pi + VIEW_IR * sqrt(P Sigma P'): the view expects the spread to beat
   its equilibrium value by VIEW_IR units of its own volatility. Users can add
   absolute ("XLK +3% over equilibrium") or relative ("XLK beats XLE by 5%")
   views on top.

3. View confidence. Omega = ((1 - c) / c) * tau * P Sigma P' (c = 0.5 gives the
   He-Litterman default). Because Omega is proportional to tau, tau cancels out
   of the posterior mean exactly: it has no effect on the weights and only
   scales the posterior covariance used for the reported volatility. The
   confidence c is the only knob that moves the portfolio. By default c is
   fixed at VIEW_CONF_BASE. Optionally (ML_ENABLED), a logistic regression
   predicts from regime features whether each view's long/short portfolio will
   make money over the next quarter and scales c accordingly. It is off by
   default: its 63-day labels overlap (a row every 21 days), so it trains on
   roughly a dozen independent observations when it first switches on, too few
   to estimate six coefficients, and on 2007-2021 it changed nothing measurable.

4. Posterior + optimisation. Standard BL posterior mean, then a long-only
   mean-variance utility maximisation (risk aversion delta) with a per-sector cap
   and an active-weight limit around w_mkt. With no views the optimiser returns
   w_mkt exactly, as BL should.

5. Defensive overlay. Daily exposure is scaled so trailing realised volatility
   stays near VOL_TARGET; the remainder earns the T-bill rate. Exposure changes
   pay transaction costs and only happen outside a no-trade band.
"""
import logging
import threading
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import nnls
import cvxpy as cp
from pypfopt import risk_models
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

MODEL_VERSION = "bl-2.0"

# ==========================================
# CONSTANTS & CONFIG
# ==========================================
# Parameters below were chosen on the 2007-2021 development period only; 2022+
# is held out for evaluation (see backend/research.py).
TRAIN_WINDOW = 504            # days of history for the covariance estimate
MKT_WEIGHT_WINDOW = 252       # days used to infer SPY's sector weights
REBALANCE_FREQ = 63           # trading days between rebalances (quarterly)
COST_PER_TRADE = 0.0005       # 5 bps per unit of notional traded (one-way)
TURNOVER_SKIP_THRESHOLD = 0.05  # skip a rebalance if it would trade < 5% of NAV

TAU = 0.05                    # prior uncertainty; cancels out of the weights (see docstring)
MARKET_ERP = 0.05             # assumed annual equity risk premium of the market
DELTA_MIN, DELTA_MAX = 0.5, 10.0
MAX_WEIGHT = 0.40             # hard cap per sector
ACTIVE_LIMIT = 0.10           # max |w - w_mkt| per sector

VIEW_SIGNALS = ("low_vol", "mom_rev")  # one relative view per signal, see signal_scores()
MOM_LOOKBACK = 252            # 12-month momentum ...
MOM_SKIP = 21                 # ... skipping the most recent month (12-1)
REV_LOOKBACK = 21             # 1-month reversal lookback
MOM_TOP_K = 3                 # long top-k vs short bottom-k sectors
VIEW_IR = 0.25                # view alpha in units of the view portfolio's vol
VIEW_CONF_BASE = 0.5          # confidence in the momentum view without ML
CONF_MIN, CONF_MAX = 0.05, 0.95

ML_ENABLED = False            # optional regime-conditional confidence; see docstring
ML_HORIZON = 63               # label: momentum spread over the next 63 days
ML_STEP = 21                  # a training row every 21 trading days
ML_MIN_ROWS = 36
ML_FEATURES = ["leader_strength", "breadth", "dispersion", "avg_corr",
               "spy_trend_12m", "spy_vol_6m"]

MANUAL_EXTRA_CAP = 0.15
CONF_CAP_LO, CONF_CAP_HI = 0.05, 0.85
DEFAULT_RF = 0.02             # fallback annual risk-free rate when ^IRX is missing

# --- Defensive volatility-targeting overlay -------------------------------
# Set VOL_TARGET = None to disable and stay fully invested.
VOL_TARGET = 0.10
VOL_TARGET_LOOKBACK = 21
EXPOSURE_FLOOR = 0.00
EXPOSURE_CAP = 1.00
EXPOSURE_BAND = 0.05          # only re-size when target exposure moves > 5 pts
VOL_ESTIMATOR = "rolling"     # "rolling" (21d stdev), "ewma" (RiskMetrics 0.94) or "max" (max of 21d, 63d)

SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
BOND_TICKER = "IEF"           # 7-10y Treasuries, used for the 60/40 benchmark


# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def download_prices(symbols, start_date):
    """Download a flattened price DataFrame for the given symbols."""
    from app.data_loader import download_and_flatten
    try:
        return download_and_flatten(symbols, start_date)
    except Exception as e:
        logger.error("Error downloading data: %s", e)
        return pd.DataFrame()


def inverse_vol_anchor(cov: pd.DataFrame) -> pd.Series:
    """Inverse-volatility weights (used only as a benchmark)."""
    vol = np.sqrt(np.diag(cov))
    w = 1.0 / (vol + 1e-12)
    w = w / w.sum()
    return pd.Series(w, index=cov.index)


def implied_market_weights(asset_rets: pd.DataFrame, mkt_rets: pd.Series) -> pd.Series:
    """Returns-based style analysis: w >= 0, sum(w) = 1, minimising the
    tracking error between the sector mix and the market (SPY).

    Solved as NNLS with a heavily weighted extra row enforcing the budget.
    """
    df = asset_rets.join(mkt_rets.rename("__mkt__"), how="inner").dropna()
    cols = list(asset_rets.columns)
    if len(df) < 60:
        return pd.Series(1.0 / len(cols), index=cols)
    X = df[cols].to_numpy()
    y = df["__mkt__"].to_numpy()
    # Penalty row: each unit of budget error costs big**2 = 1e6, versus a total
    # squared tracking error of ~0.03 for a year of daily returns, so the budget
    # binds to ~1e-9 (matches an exact constrained solve), then is renormalised.
    big = 1e3
    A = np.vstack([X, big * np.ones((1, X.shape[1]))])
    b = np.concatenate([y, [big]])
    w, _ = nnls(A, b)
    if not np.isfinite(w).all() or w.sum() <= 0:
        return pd.Series(1.0 / len(cols), index=cols)
    w = w / w.sum()
    return pd.Series(w, index=cols)


def market_equilibrium(prices_train: pd.DataFrame, market_train: pd.Series):
    """Returns (Sigma, delta, pi, w_mkt): the BL prior at the end of the window."""
    S = risk_models.CovarianceShrinkage(prices_train).ledoit_wolf()
    tail = prices_train.iloc[-(MKT_WEIGHT_WINDOW + 1):]
    w_mkt = implied_market_weights(
        tail.pct_change().dropna(), market_train.loc[tail.index].pct_change().dropna()
    ).reindex(S.index).fillna(0.0)
    mkt_var = float(w_mkt.values @ S.values @ w_mkt.values)
    delta = clamp(MARKET_ERP / mkt_var, DELTA_MIN, DELTA_MAX) if mkt_var > 1e-12 else 2.5
    pi = pd.Series(delta * (S.values @ w_mkt.values), index=S.index)
    return S, float(delta), pi, w_mkt


def momentum_scores(prices_hist: pd.DataFrame, skip: int = None) -> pd.Series:
    """12-1 month total return per sector (NaN if not enough history)."""
    skip = MOM_SKIP if skip is None else skip
    if len(prices_hist) < MOM_LOOKBACK + 1:
        return pd.Series(np.nan, index=prices_hist.columns)
    p_end = prices_hist.iloc[-1 - skip]
    p_start = prices_hist.iloc[-1 - MOM_LOOKBACK]
    return p_end / p_start - 1.0


SIGNAL_LABELS = {
    "mom_12_1": "12-1m momentum",
    "mom_12": "12m momentum",
    "rev_1": "1m reversal",
    "mom_rev": "12-1m momentum + 1m reversal",
    "low_vol": "low volatility",
}


def _zscore(x: pd.Series) -> pd.Series:
    return (x - x.mean()) / (x.std() + 1e-12)


def signal_scores(prices_hist: pd.DataFrame, kind: str) -> pd.Series:
    """Cross-sectional score used to build the model's relative view
    (higher = expected to outperform)."""
    if len(prices_hist) < MOM_LOOKBACK + 1:
        return pd.Series(np.nan, index=prices_hist.columns)
    rev = -(prices_hist.iloc[-1] / prices_hist.iloc[-1 - REV_LOOKBACK] - 1.0)
    if kind == "mom_12_1":
        return momentum_scores(prices_hist)
    if kind == "mom_12":
        return momentum_scores(prices_hist, skip=0)
    if kind == "rev_1":
        return rev
    if kind == "mom_rev":
        return _zscore(momentum_scores(prices_hist)) + _zscore(rev)
    if kind == "low_vol":
        return -prices_hist.iloc[-126:].pct_change().std()
    raise ValueError(f"unknown view signal {kind!r}")


def view_portfolio(scores: pd.Series, k: int = None) -> pd.Series:
    """Long the top-k, short the bottom-k sectors by score, equal weighted (sums to 0)."""
    k = k or MOM_TOP_K
    s = scores.dropna().sort_values()
    p = pd.Series(0.0, index=scores.index)
    if len(s) < 2 * k:
        return p
    p[s.index[-k:]] = 1.0 / k
    p[s.index[:k]] = -1.0 / k
    return p


def view_omega(p_row: np.ndarray, S: np.ndarray, conf: float, tau: float = None) -> float:
    """Omega for one view: ((1 - c) / c) * tau * p' Sigma p."""
    tau = TAU if tau is None else tau
    conf = clamp(conf, 1e-3, 1 - 1e-3)
    return float((1 - conf) / conf * tau * (p_row @ S @ p_row))


def bl_posterior(pi: pd.Series, S: pd.DataFrame, P: np.ndarray, Q: np.ndarray,
                 omega: np.ndarray, tau: float = None):
    """Black-Litterman posterior mean and covariance (He & Litterman form)."""
    tau = TAU if tau is None else tau
    idx = S.index
    if P is None or len(Q) == 0:
        return pi.copy(), S * (1 + tau)
    Sv = S.values
    tS = tau * Sv
    PtS = P @ tS
    middle = PtS @ P.T + omega
    K = tS @ P.T @ np.linalg.inv(middle)
    mu = pi.values + K @ (Q - P @ pi.values)
    M = tS - K @ PtS
    S_post = Sv + M
    return pd.Series(mu, index=idx), pd.DataFrame(S_post, index=idx, columns=idx)


_QP_CACHE = {}
_QP_LOCK = threading.Lock()


def _qp(n):
    """A parametrised (DPP) QP built once per universe size and re-solved with
    new data at every rebalance, instead of re-compiling with cvxpy each time."""
    if n not in _QP_CACHE:
        w = cp.Variable(n)
        mu = cp.Parameter(n)
        lt = cp.Parameter((n, n))     # sqrt(delta) * Sigma^(1/2)
        lo = cp.Parameter(n, nonneg=True)
        hi = cp.Parameter(n, nonneg=True)
        prob = cp.Problem(cp.Maximize(mu @ w - 0.5 * cp.sum_squares(lt @ w)),
                          [cp.sum(w) == 1, w >= lo, w <= hi])
        _QP_CACHE[n] = (prob, w, mu, lt, lo, hi)
    return _QP_CACHE[n]


def optimize_weights(mu: pd.Series, S: pd.DataFrame, delta: float, w_mkt: pd.Series,
                     max_weight: float = None, active_limit: float = None) -> pd.Series:
    """max w'mu - delta/2 w'Sigma w  s.t. sum(w)=1, 0<=w<=cap, |w - w_mkt|<=limit.

    With mu = pi (no views) the unconstrained optimum is w_mkt itself, so the
    portfolio only moves away from the market when views say so.
    """
    max_weight = MAX_WEIGHT if max_weight is None else max_weight
    active_limit = ACTIVE_LIMIT if active_limit is None else active_limit
    idx = S.index
    wm = w_mkt.reindex(idx).fillna(0.0).values
    n = len(idx)
    cap = max(max_weight, wm.max())
    lo = np.zeros(n)
    hi = np.full(n, cap)
    if active_limit is not None:
        lo = np.maximum(lo, wm - active_limit)
        hi = np.minimum(hi, wm + active_limit)
    # Sigma = V diag(lam) V'  ->  w'Sigma w = ||diag(sqrt(lam)) V' w||^2
    lam, V = np.linalg.eigh((S.values + S.values.T) / 2)
    lt = np.sqrt(max(delta, 0.0)) * (np.sqrt(np.clip(lam, 0.0, None))[:, None] * V.T)
    try:
        with _QP_LOCK:
            prob, w, mu_p, lt_p, lo_p, hi_p = _qp(n)
            mu_p.value = mu.reindex(idx).values.astype(float)
            lt_p.value = lt
            lo_p.value = lo
            hi_p.value = hi
            prob.solve(solver=cp.CLARABEL)
            if w.value is None:
                raise ValueError("solver returned no solution")
            out = np.clip(np.asarray(w.value).ravel(), 0.0, None)
        out = out / out.sum()
    except Exception as exc:
        logger.warning("optimizer failed (%s); holding market weights", exc)
        out = wm / wm.sum() if wm.sum() > 0 else np.full(n, 1.0 / n)
    out[out < 1e-4] = 0.0
    return pd.Series(out / out.sum(), index=idx)


def regime_features(prices_hist: pd.DataFrame, mkt_hist: pd.Series):
    """Regime features for the ML confidence model (None if not enough data)."""
    if len(prices_hist) < 260 or len(mkt_hist) < 260:
        return None
    rs12 = (prices_hist.iloc[-1] / prices_hist.iloc[-252]) / (mkt_hist.iloc[-1] / mkt_hist.iloc[-252]) - 1
    rs6 = (prices_hist.iloc[-1] / prices_hist.iloc[-126]) / (mkt_hist.iloc[-1] / mkt_hist.iloc[-126]) - 1
    leadership = 0.7 * rs12 + 0.3 * rs6
    rets = prices_hist.iloc[-127:].pct_change().dropna()
    corr = rets.corr().values
    return {
        "leader_strength": float(leadership.max()),
        "breadth": float((leadership > 0).mean()),
        "dispersion": float(rets.std().mean() * np.sqrt(252)),
        "avg_corr": float(corr[np.triu_indices_from(corr, k=1)].mean()),
        "spy_trend_12m": float(mkt_hist.iloc[-1] / mkt_hist.iloc[-253] - 1),
        "spy_vol_6m": float(mkt_hist.iloc[-127:].pct_change().std() * np.sqrt(252)),
    }


def detect_vol_regime(market_prices, current_date):
    mkt_hist = market_prices.loc[:current_date].dropna()
    if len(mkt_hist) < 100:
        return "low", np.nan, np.nan
    rolling_vol = mkt_hist.pct_change().rolling(63).std() * np.sqrt(252)
    hist_median = float(rolling_vol.median())
    realized_vol = float(mkt_hist.iloc[-63:].pct_change().std() * np.sqrt(252))
    regime = "high" if (np.isfinite(realized_vol) and np.isfinite(hist_median)
                        and realized_vol > hist_median) else "low"
    return regime, realized_vol, hist_median


def calc_max_drawdown(prices_series):
    roll_max = prices_series.cummax()
    drawdown = (prices_series - roll_max) / roll_max
    return float(drawdown.min())


def perf_metrics(rets: pd.Series, rf_daily: pd.Series):
    """CAGR / vol / excess Sharpe / max drawdown for a daily return series."""
    rets = rets.dropna()
    if len(rets) < 2:
        return None
    curve = (1 + rets).cumprod()
    years = len(rets) / 252.0
    rf_ann = float(rf_daily.reindex(rets.index).ffill().fillna(DEFAULT_RF / 252).mean() * 252)
    vol = float(rets.std() * np.sqrt(252))
    ann_ret = float(rets.mean() * 252)
    return {
        "total_return": float(curve.iloc[-1] - 1),
        "cagr": float(curve.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0,
        "volatility": vol,
        "sharpe": (ann_ret - rf_ann) / vol if vol > 0 else 0.0,
        "max_dd": calc_max_drawdown(curve),
    }


def realized_vol_estimate(rets: pd.Series, lookback: int = None, kind: str = None) -> pd.Series:
    """Annualised volatility estimate at each date using returns up to that date."""
    lookback = VOL_TARGET_LOOKBACK if lookback is None else lookback
    kind = VOL_ESTIMATOR if kind is None else kind
    short = rets.rolling(lookback).std()
    if kind == "ewma":
        est = np.sqrt((rets ** 2).ewm(alpha=0.06, min_periods=lookback).mean())
    elif kind == "max":
        est = pd.concat([short, rets.rolling(3 * lookback).std()], axis=1).max(axis=1, skipna=False)
    else:
        est = short
    return est * np.sqrt(252)


def apply_vol_overlay(rets: pd.Series, rf_daily: pd.Series, target=None, lookback=None,
                      band=None, cost=None):
    """Scale exposure so trailing realised vol ~ target. The signal uses returns
    up to t-1 only; exposure changes pay `cost` per unit traded.

    Returns (overlaid returns, exposure series)."""
    target = VOL_TARGET if target is None else target
    lookback = VOL_TARGET_LOOKBACK if lookback is None else lookback
    band = EXPOSURE_BAND if band is None else band
    cost = COST_PER_TRADE if cost is None else cost
    realized = realized_vol_estimate(rets, lookback)
    raw = (target / realized).clip(EXPOSURE_FLOOR, EXPOSURE_CAP).to_numpy()
    held = np.empty(len(raw))
    cur = EXPOSURE_CAP
    for t in range(len(raw)):
        held[t] = cur              # exposure during day t was set at close t-1
        v = raw[t]
        if np.isfinite(v) and abs(v - cur) > band:
            cur = v
    exposure = pd.Series(held, index=rets.index)
    rf = rf_daily.reindex(rets.index).ffill().fillna(DEFAULT_RF / 252)
    trade_cost = exposure.diff().abs().fillna(0.0) * cost
    out = exposure * rets + (1 - exposure) * rf - trade_cost
    return out, exposure


# ==========================================
# ENGINE CLASS
# ==========================================
class BLEngine:
    def __init__(self, prices_df=None):
        self.tickers = list(SECTORS)
        self.market_ticker = "SPY"
        self.risk_free_ticker = "^IRX"
        self._ml_cache = {}
        self._feat_cache = {}
        self._base_cache = {}
        # Serialises the cached builds below so a request and the startup
        # warm-up never compute the same thing twice side by side.
        self._build_lock = threading.RLock()

        if prices_df is None:
            all_syms = self.tickers + [self.market_ticker, self.risk_free_ticker, "VNQ", "VOX", BOND_TICKER]
            prices_df = download_prices(all_syms, "2005-01-01")

        self.prices = prices_df.copy()
        if self.prices.empty:
            logger.error("CRITICAL ERROR: No price data downloaded. Engine will fail.")
        else:
            self._prepare_data()

    def _prepare_data(self):
        if self.prices.index.tz is not None:
            self.prices.index = self.prices.index.tz_localize(None)

        # XLRE (2015) and XLC (2018) are back-filled with the closest older ETFs.
        if "VNQ" in self.prices.columns and "XLRE" in self.prices.columns:
            self.prices["XLRE"] = self.prices["XLRE"].fillna(self.prices["VNQ"])
        if "VOX" in self.prices.columns and "XLC" in self.prices.columns:
            self.prices["XLC"] = self.prices["XLC"].fillna(self.prices["VOX"])

        if self.market_ticker in self.prices.columns:
            self.market_prices = self.prices[self.market_ticker].dropna()
        else:
            self.market_prices = pd.Series(dtype=float)

        if self.risk_free_ticker in self.prices.columns:
            self.rf_daily = (self.prices[self.risk_free_ticker].ffill() / 100.0) / 252.0
        else:
            self.rf_daily = pd.Series(DEFAULT_RF / 252, index=self.prices.index)

        available = [t for t in self.tickers if t in self.prices.columns]
        self.tickers = available
        self.asset_prices = self.prices[available].dropna(how="any")

        common = self.asset_prices.index.intersection(self.market_prices.index)
        self.asset_prices = self.asset_prices.loc[common]
        self.market_prices = self.market_prices.loc[common]
        self.rf_daily = self.rf_daily.reindex(common).ffill().fillna(DEFAULT_RF / 252)

        if BOND_TICKER in self.prices.columns:
            self.bond_prices = self.prices[BOND_TICKER].reindex(common).ffill()
        else:
            self.bond_prices = None

        logger.info("Data prepared. Rows: %d", len(self.asset_prices))

    def _annual_rf(self, as_of_date=None):
        series = self.rf_daily if as_of_date is None else self.rf_daily.loc[:as_of_date]
        series = series.dropna()
        return float(series.iloc[-1] * 252) if not series.empty else DEFAULT_RF

    # ------------------------------------------------------------------ ML
    def _ml_dataset(self, kind):
        """Point-in-time regime features every ML_STEP days for one view signal,
        labelled 1 if that view's long/short portfolio made money over the next
        ML_HORIZON days, plus the index at which the label becomes known."""
        if kind in self._ml_cache:
            return self._ml_cache[kind]
        with self._build_lock:
            if kind not in self._ml_cache:
                self._ml_cache[kind] = self._build_ml_dataset(kind)
        return self._ml_cache[kind]

    def _build_ml_dataset(self, kind):
        px = self.asset_prices
        rows = []
        for j in range(MOM_LOOKBACK + 1, len(px) - ML_HORIZON, ML_STEP):
            hist = px.iloc[:j]
            feats = self._features_at(j)
            if feats is None:
                continue
            p = view_portfolio(signal_scores(hist, kind))
            if not p.any():
                continue
            # Executed at close j-1 (data through j-1), held to close j-1+H.
            fwd = px.iloc[j - 1 + ML_HORIZON] / px.iloc[j - 1] - 1.0
            spread = float((p * fwd).sum())
            rows.append({**feats, "label": int(spread > 0), "known_at": j - 1 + ML_HORIZON})
        return pd.DataFrame(rows)

    def _features_at(self, i):
        if i not in self._feat_cache:
            self._feat_cache[i] = regime_features(self.asset_prices.iloc[:i], self.market_prices.iloc[:i])
        return self._feat_cache[i]

    def _view_confidence(self, i, kind):
        """Confidence in a model view for a decision using data iloc[:i].

        A logistic regression, trained only on labels observable by close i-1,
        predicts whether the view will pay off. Confidence is the base
        confidence scaled by (predicted probability / historical hit rate), so
        the model only moves confidence when it sees something unusual.
        Returns (confidence, info dict)."""
        info = {"active": False, "probability": None, "base_rate": None, "train_rows": 0}
        if not ML_ENABLED:
            return VIEW_CONF_BASE, info
        feats = self._features_at(i)
        if feats is None:
            return VIEW_CONF_BASE, info
        data = self._ml_dataset(kind)
        if data.empty:
            return VIEW_CONF_BASE, info
        train = data[data["known_at"] <= i - 1]
        info["train_rows"] = int(len(train))
        if len(train) < ML_MIN_ROWS or train["label"].nunique() < 2:
            return VIEW_CONF_BASE, info
        model = Pipeline([("s", StandardScaler()), ("c", LogisticRegression(C=0.5, max_iter=2000))])
        model.fit(train[ML_FEATURES], train["label"])
        p = float(model.predict_proba(pd.DataFrame([feats])[ML_FEATURES])[0, 1])
        base = float(train["label"].mean())
        conf = clamp(VIEW_CONF_BASE * p / max(base, 1e-6), CONF_MIN, CONF_MAX)
        info.update({"active": True, "probability": p, "base_rate": base})
        return conf, info

    # ------------------------------------------------------------ decision
    def _decide_base(self, i):
        """The part of a decision that does not depend on user views (prior,
        model views, ML confidence). Cached per position i, so repeated
        backtests and user-view backtests reuse it."""
        cached = self._base_cache.get(i)
        if cached is not None:
            return cached
        with self._build_lock:
            if i not in self._base_cache:
                self._base_cache[i] = self._build_base(i)
        return self._base_cache[i]

    def _build_base(self, i):
        hist = self.asset_prices.iloc[:i]
        mkt_hist = self.market_prices.iloc[:i]
        train = hist.iloc[-TRAIN_WINDOW:]
        S, delta, pi, w_mkt = market_equilibrium(train, mkt_hist.loc[train.index])
        Sv = S.values
        tickers = list(S.index)

        P_rows, Q, omegas, view_info = [], [], [], []

        # --- Model views: one relative long/short view per signal ---
        ml_info = {}
        for kind in VIEW_SIGNALS:
            p_view = view_portfolio(signal_scores(hist, kind)).reindex(tickers).fillna(0.0)
            if p_view.abs().sum() == 0:
                continue
            conf, info = self._view_confidence(i, kind)
            ml_info[kind] = info
            pv = p_view.values
            view_vol = float(np.sqrt(pv @ Sv @ pv))
            q = float(pv @ pi.values) + VIEW_IR * view_vol
            P_rows.append(pv)
            Q.append(q)
            omegas.append(view_omega(pv, Sv, conf))
            longs = [t for t in tickers if p_view[t] > 0]
            shorts = [t for t in tickers if p_view[t] < 0]
            view_info.append({
                "source": "model", "type": "relative", "signal": kind,
                "description": f"{'/'.join(longs)} outperform {'/'.join(shorts)} ({SIGNAL_LABELS[kind]})",
                "long": longs, "short": shorts,
                "expected_spread": q, "equilibrium_spread": float(pv @ pi.values),
                "confidence": conf, "ml_probability": info["probability"],
            })

        base = {"date": hist.index[-1], "S": S, "delta": delta, "pi": pi, "w_mkt": w_mkt,
                "P_rows": P_rows, "Q": Q, "omegas": omegas, "views": view_info,
                "ml": ml_info, "train": train}
        return base

    def _decide(self, i, user_views=(), period_date=None):
        """Full BL decision using prices iloc[:i] (data through day i-1)."""
        base = self._decide_base(i)
        S, delta, pi, w_mkt = base["S"], base["delta"], base["pi"], base["w_mkt"]
        Sv = S.values
        tickers = list(S.index)
        P_rows, Q, omegas = list(base["P_rows"]), list(base["Q"]), list(base["omegas"])
        view_info = [dict(v) for v in base["views"]]

        # --- Discretionary user views ---
        applied = []
        for v in user_views:
            t = v.get("ticker")
            vs = v.get("versus") or None
            if t not in tickers or (vs is not None and vs not in tickers) or vs == t:
                continue
            sd, ed = v.get("start_date"), v.get("end_date")
            if period_date is not None:
                if sd and period_date < pd.Timestamp(sd):
                    continue
                if ed and period_date > pd.Timestamp(ed):
                    continue
            extra = float(clamp(float(v["value"]), -MANUAL_EXTRA_CAP, MANUAL_EXTRA_CAP))
            conf = float(clamp(float(v["confidence"]), CONF_CAP_LO, CONF_CAP_HI))
            pv = np.zeros(len(tickers))
            pv[tickers.index(t)] = 1.0
            if vs is not None:
                pv[tickers.index(vs)] = -1.0
            q = float(pv @ pi.values) + extra
            P_rows.append(pv)
            Q.append(q)
            omegas.append(view_omega(pv, Sv, conf))
            label = f"{t} vs {vs} {extra:+.1%}" if vs else f"{t} {extra:+.1%}"
            applied.append(label)
            view_info.append({"source": "user", "type": "relative" if vs else "absolute",
                              "description": label, "confidence": conf,
                              "expected_spread": q, "equilibrium_spread": float(pv @ pi.values)})

        if P_rows:
            P = np.vstack(P_rows)
            mu, S_post = bl_posterior(pi, S, P, np.array(Q), np.diag(omegas))
        else:
            mu, S_post = bl_posterior(pi, S, None, np.array([]), None)

        weights = optimize_weights(mu, S, delta, w_mkt)
        return {
            "date": base["date"], "S": S, "S_post": S_post, "delta": delta,
            "pi": pi, "mu": mu, "w_mkt": w_mkt, "weights": weights,
            "views": view_info, "applied": applied, "ml": base["ml"], "train": base["train"],
        }

    # ------------------------------------------------------------ scenario
    def run_scenario(self, user_views: list, target_date: str = None):
        if target_date:
            i = int(self.asset_prices.index.searchsorted(pd.Timestamp(target_date), side="right"))
        else:
            i = len(self.asset_prices)
        if i < TRAIN_WINDOW:
            return {"error": f"Not enough data for {target_date}"}

        input_warnings = self._validate_views(user_views)
        d = self._decide(i, user_views)
        current_date = d["date"]
        weights, mu, S_post, pi = d["weights"], d["mu"], d["S_post"], d["pi"]
        rf_now = self._annual_rf(current_date)
        vol_regime, _, _ = detect_vol_regime(self.market_prices, current_date)

        # pi and mu are excess returns; add the T-bill rate for total returns.
        port_ret = float(weights.values @ mu.values) + rf_now
        port_vol = float(np.sqrt(max(weights.values @ S_post.values @ weights.values, 0.0)))

        exposure = 1.0
        realized_vol = None
        if VOL_TARGET is not None:
            recent = d["train"].pct_change().iloc[-VOL_TARGET_LOOKBACK:]
            realized_vol = float(np.nanstd(recent.values @ weights.values, ddof=1) * np.sqrt(252))
            if realized_vol > 1e-9:
                exposure = float(np.clip(VOL_TARGET / realized_vol, EXPOSURE_FLOOR, EXPOSURE_CAP))

        sharpe_val = (port_ret - rf_now) / port_vol if port_vol > 1e-9 else 0.0
        ranked = sorted(weights.to_dict().items(), key=lambda kv: kv[1], reverse=True)
        top = [(t, w) for t, w in ranked if w > 0.005][:3]
        holdings_txt = ", ".join(f"{t} ({w:.0%})" for t, w in top) if top else "a broadly balanced mix"
        active = (weights - d["w_mkt"]).sort_values()
        summary = (
            f"As of {current_date.date()}, the market (SPY) equilibrium is tilted toward "
            f"{active.index[-1]} ({active.iloc[-1]:+.0%}) and away from {active.index[0]} "
            f"({active.iloc[0]:+.0%}). Largest positions: {holdings_txt}. Expected return "
            f"{port_ret:.1%} with {port_vol:.1%} volatility (Sharpe {sharpe_val:.2f}) in a "
            f"{vol_regime}-volatility regime."
        )
        if d["applied"]:
            summary += f" Your views ({', '.join(d['applied'])}) have been incorporated."
        summary += (f" Given current volatility, the model recommends being about "
                    f"{exposure:.0%} invested and {1 - exposure:.0%} in cash.")

        return {
            "date": str(current_date.date()),
            "model_version": MODEL_VERSION,
            "exposure": {"invested": exposure, "cash": 1.0 - exposure,
                         "vol_target": VOL_TARGET, "realized_vol": realized_vol},
            "weights": weights.to_dict(),
            "equilibrium_weights": d["w_mkt"].to_dict(),
            "active_weights": (weights - d["w_mkt"]).to_dict(),
            "views": d["views"],
            "ml": d["ml"],
            "regime": {"volatility": vol_regime},
            "metrics": {"delta": round(d["delta"], 2), "expected_return": port_ret,
                        "volatility": port_vol, "risk_free": rf_now},
            "expected_returns": {
                "prior": {t: float(pi[t]) + rf_now for t in self.tickers},
                "posterior": {t: float(mu[t]) + rf_now for t in self.tickers},
            },
            "summary": summary,
            "warnings": input_warnings,
            "applied_scenarios": d["applied"],
        }

    def _validate_views(self, user_views):
        out = []
        valid = set(self.tickers)
        for v in user_views:
            t, vs = v.get("ticker"), v.get("versus")
            if t not in valid:
                out.append(f"Ignored unknown ticker '{t}'. Valid tickers: {', '.join(self.tickers)}.")
                continue
            if vs and (vs not in valid or vs == t):
                out.append(f"Ignored view {t} vs '{vs}': the second ticker must be a different valid sector.")
                continue
            raw_val, raw_conf = float(v["value"]), float(v["confidence"])
            if clamp(raw_val, -MANUAL_EXTRA_CAP, MANUAL_EXTRA_CAP) != raw_val:
                out.append(f"{t}: excess return {raw_val:.1%} was capped to ±{MANUAL_EXTRA_CAP:.0%}.")
            if clamp(raw_conf, CONF_CAP_LO, CONF_CAP_HI) != raw_conf:
                out.append(f"{t}: confidence {raw_conf:.0%} was capped to "
                           f"{CONF_CAP_LO:.0%}-{CONF_CAP_HI:.0%}.")
            sd, ed = v.get("start_date"), v.get("end_date")
            if sd and ed:
                try:
                    if pd.Timestamp(sd) > pd.Timestamp(ed):
                        out.append(f"{t}: view start date is after its end date; this view may never apply.")
                except Exception:
                    out.append(f"{t}: could not parse the view's date range.")
        return out

    def run_monte_carlo(self, mu, sigma, days=252, n_sims=5000, n_samples=3, seed=42):
        rng = np.random.default_rng(seed)
        dt = 1 / 252
        paths = np.zeros((days, n_sims))
        paths[0] = 100
        for t in range(1, days):
            z = rng.standard_normal(n_sims)
            paths[t] = paths[t - 1] * np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z)
        n_samples = int(min(n_samples, n_sims))
        random_indices = rng.choice(n_sims, n_samples, replace=False)
        return {
            "days": list(range(days)),
            "p05": np.percentile(paths, 5, axis=1).tolist(),
            "p25": np.percentile(paths, 25, axis=1).tolist(),
            "p50": np.percentile(paths, 50, axis=1).tolist(),
            "p75": np.percentile(paths, 75, axis=1).tolist(),
            "p95": np.percentile(paths, 95, axis=1).tolist(),
            "sample_paths": paths[:, random_indices].T.tolist(),
            "simulation_count": n_sims,
        }

    # ------------------------------------------------------------ backtest
    @staticmethod
    def simulate_schedule(prices: pd.DataFrame, schedule, end_pos, skip_threshold=None, cost=None):
        """Drift-aware simulation of a list of (position i, target weights).

        Weights decided with data through i-1 are traded at close i-1 and held
        (drifting) until the next rebalance, so consecutive periods share their
        boundary close and no day is dropped. Costs are charged on the full
        notional traded, measured against the drifted weights.

        Returns (daily returns, list of (date, held weights), annual turnover).
        """
        skip_threshold = TURNOVER_SKIP_THRESHOLD if skip_threshold is None else skip_threshold
        cost = COST_PER_TRADE if cost is None else cost
        cols = prices.columns
        held = pd.Series(0.0, index=cols)     # starts in cash
        out, snaps, traded = [], [], 0.0
        for k, (i, target) in enumerate(schedule):
            nxt = schedule[k + 1][0] if k + 1 < len(schedule) else end_pos
            seg = prices.iloc[i - 1:nxt]          # closes i-1 .. nxt-1
            if len(seg) < 2:
                continue
            target = target.reindex(cols).fillna(0.0)
            turnover = float((target - held).abs().sum())
            if held.sum() > 0 and turnover < skip_threshold:
                w = held
                turnover = 0.0
            else:
                w = target
            traded += turnover
            rel = seg / seg.iloc[0]
            val = rel.mul(w, axis=1).sum(axis=1)
            r = val.pct_change().iloc[1:]
            if turnover > 0:
                r.iloc[0] -= turnover * cost
            out.append(r)
            snaps.append((seg.index[1], w))
            end_vals = rel.iloc[-1] * w
            held = end_vals / end_vals.sum() if end_vals.sum() > 0 else w
        if not out:
            return pd.Series(dtype=float), snaps, 0.0
        rets = pd.concat(out)
        years = max(len(rets) / 252.0, 1e-9)
        return rets, snaps, traded / years

    def run_backtest(self, start_date: str, end_date: str, user_views: list, initial_capital=10000.0,
                     include_benchmarks=True, overlay=True, return_series=False):
        """Walk-forward backtest. With return_series=True the result also holds
        each strategy's daily returns under "series" (pandas objects, for
        research scripts only; not JSON-serialisable)."""
        try:
            ts_start, ts_end = pd.Timestamp(start_date), pd.Timestamp(end_date)
        except Exception:
            return {"error": "Invalid date format. Please use YYYY-MM-DD."}
        if ts_start >= ts_end:
            return {"error": "Start date must be before end date."}

        input_warnings = self._validate_views(user_views)
        idx = self.asset_prices.index
        start_pos = max(int(idx.searchsorted(ts_start)), TRAIN_WINDOW, 1)
        end_pos = int(idx.searchsorted(ts_end, side="right"))   # exclusive
        if end_pos - start_pos < 2:
            return {"error": "No simulation data generated"}

        schedule, mkt_schedule, iv_schedule, decisions = [], [], [], []
        for i in range(start_pos, end_pos - 1, REBALANCE_FREQ):
            d = self._decide(i, user_views, period_date=idx[i])
            schedule.append((i, d["weights"]))
            mkt_schedule.append((i, d["w_mkt"]))
            iv_schedule.append((i, inverse_vol_anchor(d["S"])))
            decisions.append(d)
        if not schedule:
            return {"error": "No simulation data generated"}

        px = self.asset_prices[self.tickers]
        raw_rets, snaps, turnover_ann = self.simulate_schedule(px, schedule, end_pos)
        if raw_rets.empty:
            return {"error": "No simulation data generated"}

        if overlay and VOL_TARGET is not None:
            port_rets, exposure = apply_vol_overlay(raw_rets, self.rf_daily)
        else:
            port_rets, exposure = raw_rets, pd.Series(1.0, index=raw_rets.index)

        dates = port_rets.index
        spy_rets = self.market_prices.pct_change().reindex(dates).fillna(0.0)
        rf = self.rf_daily

        port_curve = (1 + port_rets).cumprod() * initial_capital
        spy_curve = (1 + spy_rets).cumprod() * initial_capital
        df_res = pd.DataFrame({"Portfolio": port_curve, "SPY": spy_curve})

        # ---- yearly table
        year_end_vals = df_res.resample("YE").last()
        start_row = pd.DataFrame({"Portfolio": initial_capital, "SPY": initial_capital},
                                 index=[df_res.index[0] - pd.Timedelta(days=1)])
        yearly_res = pd.concat([start_row, year_end_vals]).pct_change().dropna()
        yearly_table = []
        for dt, row in yearly_res.iterrows():
            in_year = [w for (wd, w) in snaps if wd.year == dt.year]
            holdings_str = "Balanced"
            if in_year:
                top_3 = pd.DataFrame(in_year).mean().sort_values(ascending=False).head(3)
                parts = [f"{t}({w:.0%})" for t, w in top_3.items() if w > 0.01]
                holdings_str = " ".join(parts) or holdings_str
            yearly_table.append({
                "year": dt.year, "portfolio": row["Portfolio"], "spy": row["SPY"],
                "diff": row["Portfolio"] - row["SPY"], "top_holdings": holdings_str,
                "avg_exposure": float(exposure[exposure.index.year == dt.year].mean()),
            })

        m_port = perf_metrics(port_rets, rf)
        m_spy = perf_metrics(spy_rets, rf)
        rf_ann = float(rf.reindex(dates).mean() * 252)

        # ---- benchmarks (same dates, same costs)
        benchmarks = []
        series = {}
        if include_benchmarks:
            def add(name, rets, note):
                r = rets.reindex(dates).fillna(0.0)
                m = perf_metrics(r, rf)
                if m:
                    benchmarks.append({"name": name, "note": note, **m})
                    series[name] = r
            add("Black-Litterman (this model)", port_rets,
                "Equilibrium + views" + (" + vol overlay" if overlay and VOL_TARGET is not None else ""))
            add("SPY buy & hold", spy_rets, "The market")
            if VOL_TARGET is not None:
                spy_vt, _ = apply_vol_overlay(spy_rets, rf)
                add("SPY with the same vol overlay", spy_vt,
                    "Isolates what the sector views add beyond the overlay")
                if overlay:
                    add("Black-Litterman, no overlay", raw_rets, "Sector portfolio fully invested")
            eq_rets, _, _ = self.simulate_schedule(px, mkt_schedule, end_pos)
            add("Market equilibrium (no views)", eq_rets, "BL prior weights, fully invested")
            iv_rets, _, _ = self.simulate_schedule(px, iv_schedule, end_pos)
            add("Inverse-volatility sectors", iv_rets, "The previous model's anchor")
            ew = pd.Series(1.0 / len(self.tickers), index=self.tickers)
            ew_rets, _, _ = self.simulate_schedule(px, [(i, ew) for i, _ in schedule], end_pos)
            add("Equal-weight sectors", ew_rets, "Rebalanced on the same schedule")
            if self.bond_prices is not None and self.bond_prices.iloc[:end_pos].notna().any():
                sb = pd.concat([self.market_prices.rename("SPY"), self.bond_prices.rename(BOND_TICKER)],
                               axis=1).ffill()
                if sb.iloc[start_pos - 1:end_pos].notna().all().all():
                    w6040 = pd.Series({"SPY": 0.6, BOND_TICKER: 0.4})
                    r6040, _, _ = self.simulate_schedule(sb, [(i, w6040) for i, _ in schedule], end_pos)
                    add("60/40 SPY / IEF", r6040, "Classic balanced portfolio")

        ml_active = [any(v["active"] for v in d["ml"].values()) for d in decisions]
        total_return, spy_total_return = m_port["total_return"], m_spy["total_return"]
        verb = "outperformed" if total_return >= spy_total_return else "underperformed"
        summary = (
            f"From {dates[0].date()} to {dates[-1].date()}, the strategy returned "
            f"{total_return:.1%} versus {spy_total_return:.1%} for SPY - it {verb} the benchmark by "
            f"{abs(total_return - spy_total_return):.1%}. Risk-adjusted, its Sharpe was "
            f"{m_port['sharpe']:.2f} (SPY {m_spy['sharpe']:.2f}) with a max drawdown of "
            f"{m_port['max_dd']:.1%} (SPY {m_spy['max_dd']:.1%}). It was on average "
            f"{exposure.mean():.0%} invested."
        )

        out = {
            "dates": [str(d.date()) for d in dates],
            "portfolio": port_curve.tolist(),
            "spy": spy_curve.tolist(),
            "overlay": bool(overlay and VOL_TARGET is not None),
            "metrics": {
                "total_return": total_return,
                "spy_total_return": spy_total_return,
                "cagr": m_port["cagr"],
                "spy_cagr": m_spy["cagr"],
                "sharpe": m_port["sharpe"],
                "spy_sharpe": m_spy["sharpe"],
                "max_dd": m_port["max_dd"],
                "spy_max_dd": m_spy["max_dd"],
                "volatility": m_port["volatility"],
                "spy_volatility": m_spy["volatility"],
                "risk_free": rf_ann,
                "avg_exposure": float(exposure.mean()),
                "sector_turnover": turnover_ann,
                "ml_active_share": float(np.mean(ml_active)) if ml_active else 0.0,
            },
            "benchmarks": benchmarks,
            "yearly_table": yearly_table,
            "summary": summary,
            "warnings": input_warnings,
        }
        if return_series:
            series["SPY buy & hold"] = spy_rets
            out["series"] = series
            out["rf_daily"] = rf.reindex(dates).ffill()
        return out
