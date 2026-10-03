"""Unit tests for the volatility-managed Growth engine (synthetic data, no network)."""

import json

import numpy as np
import pandas as pd
import pytest

from app.growth_engine import (
    GrowthEngine,
    MAX_LEVERAGE,
    MAX_LEVERAGE_RANGE,
    TARGET_VOL,
    TARGET_VOL_RANGE,
    VOL_LOOKBACK,
)


def _prices(daily_vol, n=1500, drift=0.0004, seed=7, shock=None):
    """SPY price path with constant vol, optionally a high-vol shock window."""
    rng = np.random.default_rng(seed)
    vol = np.full(n, daily_vol)
    if shock is not None:
        lo, hi, shock_vol = shock
        vol[lo:hi] = shock_vol
    rets = rng.normal(drift, vol)
    idx = pd.bdate_range("2015-01-01", periods=n)
    return pd.DataFrame({"SPY": 100 * np.cumprod(1 + rets), "^IRX": 2.0}, index=idx)


def test_exposure_never_exceeds_cap_and_is_non_negative():
    eng = GrowthEngine(_prices(0.004))  # very calm -> wants > cap
    res = eng.run_backtest("2015-06-01", "2020-12-31")
    assert max(res["exposure"]) <= MAX_LEVERAGE + 1e-9
    assert min(res["exposure"]) >= 0.0


def test_calm_market_is_levered_and_turbulent_market_is_derisked():
    calm = GrowthEngine(_prices(0.004)).run_scenario()
    wild = GrowthEngine(_prices(0.04)).run_scenario()
    assert calm["exposure"]["target_exposure"] > 1.0
    assert calm["exposure"]["borrowed_weight"] > 0
    assert wild["exposure"]["target_exposure"] < 0.5
    assert wild["exposure"]["cash_weight"] > 0.5
    assert wild["regime"]["volatility"] == "turbulent"


def test_exposure_drops_after_a_volatility_shock():
    prices = _prices(0.006, shock=(900, 1000, 0.05))
    eng = GrowthEngine(prices)
    res = eng.run_backtest("2015-06-01", "2020-12-31")
    exp = pd.Series(res["exposure"], index=pd.to_datetime(res["exposure_dates"]))
    before = exp.loc[prices.index[850]:prices.index[890]].mean()
    during = exp.loc[prices.index[930]:prices.index[1000]].mean()
    assert during < before * 0.6


def test_signal_is_lagged_no_lookahead():
    """Exposure on day t must be identical if day t's return is changed."""
    base = _prices(0.01)
    tampered = base.copy()
    t = 1200
    tampered.iloc[t:, 0] *= 1.5  # big jump on day t (and level shift after)
    _, e1 = GrowthEngine(base)._simulate(TARGET_VOL, MAX_LEVERAGE)
    _, e2 = GrowthEngine(tampered)._simulate(TARGET_VOL, MAX_LEVERAGE)
    day = base.index[t]
    assert e1.loc[day] == pytest.approx(e2.loc[day])


def test_leverage_one_with_flat_vol_tracks_spy_closely():
    """With a 1.0x cap and vol well above target, the strategy is mostly de-risked,
    so it must never exceed SPY's drawdown."""
    eng = GrowthEngine(_prices(0.02))
    res = eng.run_backtest("2015-06-01", "2020-12-31", target_vol=0.20, max_leverage=1.0)
    assert res["metrics"]["max_dd"] >= res["metrics"]["spy_max_dd"] - 1e-9


def test_backtest_shape_and_json_safe():
    res = GrowthEngine(_prices(0.01)).run_backtest("2015-06-01", "2020-12-31")
    json.dumps(res, allow_nan=False)  # raises on NaN/inf
    n = len(res["dates"])
    assert n == len(res["portfolio"]) == len(res["spy"]) > 100
    for key in ("total_return", "spy_total_return", "sharpe", "spy_sharpe", "max_dd",
                "spy_max_dd", "volatility", "spy_volatility", "cagr", "spy_cagr"):
        assert key in res["metrics"]
    assert res["yearly_table"] and {"year", "portfolio", "spy", "diff", "top_holdings"} <= set(res["yearly_table"][0])
    assert res["metrics"]["max_dd"] <= 0


def test_input_validation():
    eng = GrowthEngine(_prices(0.01))
    assert "error" in eng.run_backtest("not-a-date", "2020-01-01")
    assert "error" in eng.run_backtest("2020-01-01", "2019-01-01")
    assert "error" in eng.run_backtest("2015-06-01", "2015-06-05")  # too short
    res = eng.run_backtest("2015-06-01", "2020-12-31", target_vol=5.0, max_leverage=10.0)
    assert len(res["warnings"]) == 2
    assert max(res["exposure"]) <= MAX_LEVERAGE_RANGE[1]
    assert TARGET_VOL_RANGE[0] <= TARGET_VOL <= TARGET_VOL_RANGE[1]


def test_scenario_as_of_date_uses_only_past_data():
    prices = _prices(0.01, shock=(1000, 1100, 0.06))
    eng = GrowthEngine(prices)
    before = eng.run_scenario(str(prices.index[990].date()))
    after = eng.run_scenario(str(prices.index[1090].date()))
    assert after["exposure"]["realized_vol"] > before["exposure"]["realized_vol"]
    assert after["exposure"]["target_exposure"] < before["exposure"]["target_exposure"]
    assert "error" in eng.run_scenario(str(prices.index[3].date()))


def test_needs_spy_column():
    with pytest.raises(ValueError):
        GrowthEngine(pd.DataFrame({"XLK": [1.0, 2.0]}, index=pd.bdate_range("2020-01-01", periods=2)))


def test_vol_lookback_constant_is_sane():
    assert 5 <= VOL_LOOKBACK <= 126
