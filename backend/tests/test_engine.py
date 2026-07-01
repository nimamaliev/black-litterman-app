"""Unit tests for the Black-Litterman engine.

Run from the backend/ directory so that the `app` package is importable:

    cd backend
    pip install pytest        # one-time
    pytest                    # or: pytest tests/test_engine.py -v

These tests use synthetic price data, so they do NOT hit the network and do
not depend on Yahoo Finance being reachable.
"""

import numpy as np
import pandas as pd
import pytest

from app.engine import (
    BLEngine,
    clamp,
    inverse_vol_anchor,
    calc_max_drawdown,
    get_equilibrium_from_anchor,
    optimize_bl_portfolio,
    MANUAL_EXTRA_CAP,
    CONF_CAP_HI,
    DELTA_MIN,
    DELTA_MAX,
)

TICKERS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
           "XLP", "XLRE", "XLU", "XLV", "XLY"]


@pytest.fixture
def synthetic_prices():
    """Build a realistic-ish, network-free price panel.

    A shared market factor gives the sectors positive correlation, which keeps
    the implied-equilibrium returns above the risk-free rate so the max-Sharpe
    optimizer always has a feasible solution.
    """
    rng = np.random.default_rng(7)
    n_days = 900
    dates = pd.bdate_range("2017-01-02", periods=n_days)
    market_factor = rng.normal(0.0004, 0.010, n_days)
    data = {}
    for sym in TICKERS + ["SPY", "VNQ", "VOX"]:
        idio = rng.normal(0.0002, 0.008, n_days)
        rets = market_factor + idio
        data[sym] = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=dates)
    # ^IRX is quoted as an annual percentage yield (e.g. 2.0 == 2%).
    data["^IRX"] = pd.Series(2.0, index=dates)
    return pd.DataFrame(data)


# --- Pure helper functions (fully deterministic) ---------------------------

def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-3, 0, 10) == 0
    assert clamp(42, 0, 10) == 10


def test_inverse_vol_anchor_sums_to_one_and_favours_low_vol():
    cov = pd.DataFrame(
        np.diag([0.04, 0.01, 0.09]),
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )
    w = inverse_vol_anchor(cov)
    assert abs(w.sum() - 1.0) < 1e-9
    assert (w > 0).all()
    # B has the lowest variance, so it should get the largest weight.
    assert w["B"] > w["A"] > w["C"]


def test_calc_max_drawdown():
    # Peak 120 -> trough 90 is a 25% drawdown.
    assert abs(calc_max_drawdown(pd.Series([100, 120, 90, 110])) + 0.25) < 1e-9
    # A monotonically rising series never draws down.
    assert calc_max_drawdown(pd.Series([1.0, 2.0, 3.0, 4.0])) == 0.0


# --- Equilibrium + optimizer ----------------------------------------------

def test_equilibrium_delta_within_bounds(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    train = engine.asset_prices.iloc[-504:]
    train_mkt = engine.market_prices.loc[train.index]
    _, delta, pi, w_anchor = get_equilibrium_from_anchor(train, train_mkt)
    assert DELTA_MIN <= delta <= DELTA_MAX
    assert abs(w_anchor.sum() - 1.0) < 1e-3
    assert len(pi) == len(engine.tickers)


def test_optimize_no_views_returns_anchor(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    train = engine.asset_prices.iloc[-504:]
    train_mkt = engine.market_prices.loc[train.index]
    S, delta, pi, w_anchor = get_equilibrium_from_anchor(train, train_mkt)
    weights, ret_post, _ = optimize_bl_portfolio(
        S, pi, {}, pd.Series(dtype=float), delta, engine.tickers, w_anchor, 0.40
    )
    assert abs(weights.sum() - 1.0) < 1e-3
    # With no views the posterior must collapse back to the prior pi.
    assert np.allclose(ret_post.reindex(pi.index).values, pi.values)


def test_optimize_respects_weight_cap(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    train = engine.asset_prices.iloc[-504:]
    train_mkt = engine.market_prices.loc[train.index]
    S, delta, pi, w_anchor = get_equilibrium_from_anchor(train, train_mkt)
    # A very strong, confident view on one sector.
    view_dict = {"XLK": float(pi["XLK"]) + MANUAL_EXTRA_CAP}
    conf = pd.Series({"XLK": CONF_CAP_HI})
    weights, _, _ = optimize_bl_portfolio(
        S, pi, view_dict, conf, delta, engine.tickers, w_anchor, 0.40,
        risk_free_rate=0.02,
    )
    assert weights.max() <= 0.40 + 1e-6
    assert weights.min() >= -1e-6
    assert abs(weights.sum() - 1.0) < 1e-3


# --- Full scenario / backtest pipelines ------------------------------------

def test_run_scenario_structure(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    result = engine.run_scenario([{"ticker": "XLK", "value": 0.10, "confidence": 0.7}])
    assert "error" not in result
    weights = result["weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-3
    assert all(-1e-9 <= w <= 0.40 + 1e-6 for w in weights.values())
    for key in ("expected_return", "volatility", "risk_free"):
        assert key in result["metrics"]
    assert isinstance(result["summary"], str) and result["summary"]
    assert "warnings" in result


def test_run_scenario_warns_on_capped_inputs(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    result = engine.run_scenario([{"ticker": "XLK", "value": 0.99, "confidence": 0.99}])
    assert "error" not in result
    # Both the excess return and the confidence are out of range.
    assert len(result["warnings"]) >= 1


def test_run_scenario_warns_on_unknown_ticker(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    result = engine.run_scenario([{"ticker": "ZZZZ", "value": 0.05, "confidence": 0.5}])
    assert any("ZZZZ" in w for w in result["warnings"])


def test_run_backtest_structure(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    result = engine.run_backtest("2018-06-01", "2020-06-01", [])
    assert "error" not in result
    assert len(result["dates"]) > 0
    assert "yearly_table" in result
    assert isinstance(result["summary"], str) and result["summary"]
    for key in ("sharpe", "max_dd", "volatility", "risk_free"):
        assert key in result["metrics"]


def test_run_backtest_rejects_inverted_dates(synthetic_prices):
    engine = BLEngine(synthetic_prices)
    result = engine.run_backtest("2020-01-01", "2019-01-01", [])
    assert "error" in result
