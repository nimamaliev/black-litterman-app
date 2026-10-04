"""Unit tests for the Black-Litterman engine.

Run from the backend/ directory:

    cd backend
    pytest -q

These tests use synthetic price data, so they do NOT hit the network.
"""

import numpy as np
import pandas as pd
import pytest

import app.engine as eng
from app.engine import (
    BLEngine,
    clamp,
    inverse_vol_anchor,
    implied_market_weights,
    market_equilibrium,
    bl_posterior,
    optimize_weights,
    view_omega,
    view_portfolio,
    apply_vol_overlay,
    calc_max_drawdown,
    MANUAL_EXTRA_CAP,
    CONF_CAP_HI,
    DELTA_MIN,
    DELTA_MAX,
)

TICKERS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
           "XLP", "XLRE", "XLU", "XLV", "XLY"]

# Cap-like weights used to build a synthetic SPY from the sectors.
TRUE_W = pd.Series([0.03, 0.08, 0.04, 0.12, 0.09, 0.28, 0.06, 0.03, 0.03, 0.12, 0.12], index=TICKERS)


@pytest.fixture
def synthetic_prices():
    """Network-free price panel where SPY is a fixed-weight mix of the sectors."""
    rng = np.random.default_rng(7)
    n_days = 1100
    dates = pd.bdate_range("2016-01-04", periods=n_days)
    market_factor = rng.normal(0.0004, 0.010, n_days)
    sector_rets = {}
    for sym in TICKERS:
        beta = rng.uniform(0.6, 1.4)
        sector_rets[sym] = beta * market_factor + rng.normal(0.0001, 0.008, n_days)
    rets = pd.DataFrame(sector_rets, index=dates)
    data = {s: 100.0 * np.exp(np.cumsum(rets[s])) for s in TICKERS}
    spy_rets = rets.values @ TRUE_W.values
    data["SPY"] = 100.0 * np.cumprod(1 + spy_rets)
    data["VNQ"] = data["XLRE"]
    data["VOX"] = data["XLC"]
    data["IEF"] = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.004, n_days)))
    data["^IRX"] = np.full(n_days, 2.0)  # quoted as an annual percentage yield
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def engine(synthetic_prices):
    return BLEngine(synthetic_prices)


def _prior(engine):
    train = engine.asset_prices.iloc[-504:]
    return market_equilibrium(train, engine.market_prices.loc[train.index])


# --- Pure helpers ------------------------------------------------------------

def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-3, 0, 10) == 0
    assert clamp(42, 0, 10) == 10


def test_inverse_vol_anchor_sums_to_one_and_favours_low_vol():
    cov = pd.DataFrame(np.diag([0.04, 0.01, 0.09]), index=list("ABC"), columns=list("ABC"))
    w = inverse_vol_anchor(cov)
    assert abs(w.sum() - 1.0) < 1e-9
    assert w["B"] > w["A"] > w["C"]


def test_calc_max_drawdown():
    assert abs(calc_max_drawdown(pd.Series([100, 120, 90, 110])) + 0.25) < 1e-9
    assert calc_max_drawdown(pd.Series([1.0, 2.0, 3.0, 4.0])) == 0.0


def test_implied_market_weights_recovers_true_mix(synthetic_prices):
    rets = synthetic_prices[TICKERS].pct_change().dropna().iloc[-252:]
    spy = synthetic_prices["SPY"].pct_change().dropna().iloc[-252:]
    w = implied_market_weights(rets, spy)
    assert abs(w.sum() - 1.0) < 1e-9
    assert (w >= 0).all()
    assert np.allclose(w.values, TRUE_W.values, atol=0.02)


def test_view_portfolio_is_dollar_neutral():
    scores = pd.Series(np.arange(11, dtype=float), index=TICKERS)
    p = view_portfolio(scores, k=3)
    assert abs(p.sum()) < 1e-12
    assert set(p[p > 0].index) == {"XLV", "XLU", "XLY"}
    assert set(p[p < 0].index) == {"XLB", "XLC", "XLE"}


# --- Black-Litterman core ----------------------------------------------------

def test_equilibrium_delta_within_bounds_and_pi_reverse_optimised(engine):
    S, delta, pi, w_mkt = _prior(engine)
    assert DELTA_MIN <= delta <= DELTA_MAX
    assert abs(w_mkt.sum() - 1.0) < 1e-9
    assert np.allclose(pi.values, delta * S.values @ w_mkt.values)


def test_no_views_returns_market_weights_and_prior(engine):
    S, delta, pi, w_mkt = _prior(engine)
    mu, S_post = bl_posterior(pi, S, None, np.array([]), None)
    assert np.allclose(mu.values, pi.values)
    w = optimize_weights(mu, S, delta, w_mkt)
    assert np.allclose(w.values, w_mkt.values, atol=2e-3)


def test_posterior_moves_toward_view_more_with_higher_confidence(engine):
    S, delta, pi, _ = _prior(engine)
    p = np.zeros(len(S))
    p[S.index.get_loc("XLE")] = 1.0
    q = float(pi["XLE"]) + 0.10
    mu_lo, _ = bl_posterior(pi, S, p[None, :], np.array([q]), np.array([[view_omega(p, S.values, 0.2)]]))
    mu_hi, _ = bl_posterior(pi, S, p[None, :], np.array([q]), np.array([[view_omega(p, S.values, 0.8)]]))
    assert pi["XLE"] < mu_lo["XLE"] < mu_hi["XLE"] < q + 1e-9


def test_relative_view_tilts_long_leg_up_and_short_leg_down(engine):
    S, delta, pi, w_mkt = _prior(engine)
    p = np.zeros(len(S))
    p[S.index.get_loc("XLE")] = 1.0
    p[S.index.get_loc("XLK")] = -1.0
    q = float(p @ pi.values) + 0.05
    mu, _ = bl_posterior(pi, S, p[None, :], np.array([q]), np.array([[view_omega(p, S.values, 0.6)]]))
    w = optimize_weights(mu, S, delta, w_mkt)
    assert w["XLE"] > w_mkt["XLE"]
    assert w["XLK"] < w_mkt["XLK"]


def test_optimizer_respects_cap_and_active_limit(engine):
    S, delta, pi, w_mkt = _prior(engine)
    mu = pi.copy()
    mu["XLE"] += 0.50  # absurdly bullish
    w = optimize_weights(mu, S, delta, w_mkt, max_weight=0.40, active_limit=0.10)
    assert abs(w.sum() - 1.0) < 1e-6
    assert w.min() >= -1e-9
    assert (w - w_mkt).abs().max() <= 0.10 + 1e-4
    assert w.max() <= max(0.40, w_mkt.max()) + 1e-4


def test_vol_overlay_cuts_exposure_when_vol_spikes():
    idx = pd.bdate_range("2020-01-01", periods=120)
    rng = np.random.default_rng(1)
    calm = rng.normal(0, 0.003, 60)
    wild = rng.normal(0, 0.04, 60)
    rets = pd.Series(np.concatenate([calm, wild]), index=idx)
    rf = pd.Series(0.0, index=idx)
    out, exposure = apply_vol_overlay(rets, rf, target=0.10, lookback=21, band=0.0, cost=0.0)
    assert exposure.iloc[50] == pytest.approx(1.0)
    assert exposure.iloc[-1] < 0.3
    # Exposure on day t only uses returns up to t-1.
    assert exposure.iloc[0] == 1.0


def test_vol_overlay_charges_costs():
    idx = pd.bdate_range("2020-01-01", periods=80)
    rets = pd.Series(np.r_[np.full(40, 0.001), np.tile([0.03, -0.03], 20)], index=idx)
    rf = pd.Series(0.0, index=idx)
    free, e1 = apply_vol_overlay(rets, rf, target=0.10, band=0.0, cost=0.0)
    paid, e2 = apply_vol_overlay(rets, rf, target=0.10, band=0.0, cost=0.001)
    assert (e1 == e2).all()
    assert paid.sum() < free.sum()


# --- Simulation mechanics ----------------------------------------------------

def test_simulate_schedule_is_contiguous_and_charges_full_turnover():
    idx = pd.bdate_range("2020-01-01", periods=10)
    prices = pd.DataFrame({"A": np.linspace(100, 109, 10), "B": np.full(10, 50.0)}, index=idx)
    w_a = pd.Series({"A": 1.0, "B": 0.0})
    w_b = pd.Series({"A": 0.0, "B": 1.0})
    rets, _, _ = BLEngine.simulate_schedule(prices, [(1, w_a), (5, w_b)], end_pos=10,
                                            skip_threshold=0.0, cost=0.001)
    # Every day after the first decision close is covered exactly once.
    assert list(rets.index) == list(idx[1:])
    # Entering from cash trades 1.0; switching A -> B trades 2.0 of notional.
    assert rets.iloc[0] == pytest.approx(prices["A"].iloc[1] / prices["A"].iloc[0] - 1 - 0.001)
    assert rets.iloc[4] == pytest.approx(0.0 - 0.002)


# --- Full pipelines ----------------------------------------------------------

def test_run_scenario_structure(engine):
    result = engine.run_scenario([{"ticker": "XLK", "value": 0.10, "confidence": 0.7}])
    assert "error" not in result
    w = result["weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-3
    for k, x in w.items():
        assert -1e-9 <= x <= max(0.40, result["equilibrium_weights"][k]) + 1e-4
    for key in ("expected_return", "volatility", "risk_free"):
        assert key in result["metrics"]
    assert abs(sum(result["equilibrium_weights"].values()) - 1.0) < 1e-6
    assert any(v["source"] == "model" for v in result["views"])
    assert any(v["source"] == "user" for v in result["views"])
    assert isinstance(result["summary"], str) and result["summary"]


def test_run_scenario_relative_user_view(engine):
    eng_views = [{"ticker": "XLE", "versus": "XLK", "value": 0.10, "confidence": 0.8}]
    base = engine.run_scenario([])
    tilted = engine.run_scenario(eng_views)
    assert tilted["weights"]["XLE"] > base["weights"]["XLE"]
    assert tilted["weights"]["XLK"] < base["weights"]["XLK"]
    assert tilted["applied_scenarios"] == ["XLE vs XLK +10.0%"]


def test_run_scenario_warns_on_capped_and_unknown_inputs(engine):
    result = engine.run_scenario([
        {"ticker": "XLK", "value": 0.99, "confidence": 0.99},
        {"ticker": "ZZZZ", "value": 0.05, "confidence": 0.5},
    ])
    assert "error" not in result
    assert any("capped" in w for w in result["warnings"])
    assert any("ZZZZ" in w for w in result["warnings"])
    assert MANUAL_EXTRA_CAP < 0.99 and CONF_CAP_HI < 0.99


def test_run_backtest_structure_and_benchmarks(engine):
    result = engine.run_backtest("2018-06-01", "2020-06-01", [])
    assert "error" not in result
    assert len(result["dates"]) > 0
    for key in ("sharpe", "max_dd", "volatility", "risk_free", "avg_exposure", "cagr"):
        assert key in result["metrics"]
    names = {b["name"] for b in result["benchmarks"]}
    assert {"SPY buy & hold", "Market equilibrium (no views)", "Inverse-volatility sectors",
            "Equal-weight sectors", "60/40 SPY / IEF"} <= names


def test_run_backtest_without_overlay_is_fully_invested(engine):
    result = engine.run_backtest("2018-06-01", "2020-06-01", [], overlay=False)
    assert result["metrics"]["avg_exposure"] == pytest.approx(1.0)
    assert result["overlay"] is False


def test_run_backtest_rejects_inverted_dates(engine):
    assert "error" in engine.run_backtest("2020-01-01", "2019-01-01", [])


def test_ml_labels_are_only_used_once_observable(engine, monkeypatch):
    monkeypatch.setattr(eng, "ML_MIN_ROWS", 5)
    i = 700
    data = engine._ml_dataset(eng.VIEW_SIGNALS[0])
    usable = data[data["known_at"] <= i - 1]
    assert len(usable) < len(data)
    assert usable["known_at"].max() <= i - 1
    _, info = engine._view_confidence(i, eng.VIEW_SIGNALS[0])
    assert info["train_rows"] == len(usable)
