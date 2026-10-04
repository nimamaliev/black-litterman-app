"""Growth strategy: volatility-managed exposure to the broad US equity market (SPY).

Idea (volatility-managed portfolios, Moreira & Muir 2017): equity risk is far more
predictable than equity return. Holding MORE equity when trailing volatility is low
and LESS when it spikes raises return per unit of risk. Because calm markets are
also the ones that trend upward, scaling up to a leverage cap (default 1.5x) lets
the strategy out-compound plain buy-and-hold SPY, while the automatic de-risking
in turbulent markets cuts the worst drawdowns.

    exposure[t] = clip(TARGET_VOL / realized_vol[t-1], 0, MAX_LEVERAGE)

* realized_vol is the trailing 21-day annualised volatility of SPY, and the signal
  is lagged one day so there is no look-ahead.
* Exposure above 1.0x is financed at the risk-free rate (^IRX) plus a spread.
  Exposure below 1.0x earns the risk-free rate on the cash portion.
* A rebalance band avoids trading on tiny exposure changes; every change in
  exposure pays a transaction cost.

Honest caveats: it needs leverage (margin or leveraged ETFs) to beat SPY on return,
so it takes on more risk than the Defensive model; it does not pick sectors; and
it gives up some upside versus SPY in V-shaped recoveries because exposure is cut
after volatility has already risen.
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TARGET_VOL = 0.20           # annualised volatility the strategy aims for
MAX_LEVERAGE = 1.5          # hard cap on exposure to SPY
VOL_LOOKBACK = 21           # trading days used to estimate realised volatility
FINANCING_SPREAD = 0.015    # annual spread over the risk-free rate on borrowed money
COST_PER_TRADE = 0.0005     # 5 bps per unit of exposure traded
REBALANCE_BAND = 0.10       # only re-size when exposure moves by more than this
DEFAULT_RF = 0.02

TARGET_VOL_RANGE = (0.05, 0.40)
MAX_LEVERAGE_RANGE = (1.0, 2.0)


def calc_max_drawdown(curve: pd.Series) -> float:
    return float((curve / curve.cummax() - 1).min())


class GrowthEngine:
    def __init__(self, prices_df: pd.DataFrame):
        self.prices = prices_df.copy()
        if self.prices.index.tz is not None:
            self.prices.index = self.prices.index.tz_localize(None)
        if "SPY" not in self.prices.columns:
            raise ValueError("GrowthEngine needs an SPY price column.")

        self.spy = self.prices["SPY"].dropna()
        if "^IRX" in self.prices.columns:
            rf_ann = (self.prices["^IRX"].ffill() / 100.0).reindex(self.spy.index).ffill().fillna(DEFAULT_RF)
        else:
            rf_ann = pd.Series(DEFAULT_RF, index=self.spy.index)
        self.rf_ann = rf_ann
        self.rf_daily = rf_ann / 252.0
        self.spy_ret = self.spy.pct_change().fillna(0.0)

    # ------------------------------------------------------------------ core
    def _target_exposure(self, target_vol: float, max_leverage: float) -> pd.Series:
        """Unlagged target exposure computed from information up to and including t."""
        realized = self.spy_ret.rolling(VOL_LOOKBACK).std() * np.sqrt(252)
        return (target_vol / realized).clip(0.0, max_leverage)

    @staticmethod
    def _apply_band(target: pd.Series, band: float) -> pd.Series:
        """Hold the current exposure until the target moves by more than `band`."""
        out = np.empty(len(target))
        cur = np.nan
        for i, v in enumerate(target.to_numpy()):
            if np.isnan(v):
                out[i] = np.nan
                continue
            if np.isnan(cur) or abs(v - cur) > band:
                cur = v
            out[i] = cur
        return pd.Series(out, index=target.index)

    def _simulate(self, target_vol: float, max_leverage: float):
        """Returns (strategy daily returns, exposure held each day)."""
        target = self._target_exposure(target_vol, max_leverage)
        # Decide at the close of t-1, hold through t (no look-ahead).
        decided = self._apply_band(target, REBALANCE_BAND).shift(1)
        valid = decided.dropna().index
        exposure = decided.loc[valid]
        spy_ret = self.spy_ret.loc[valid]
        rf = self.rf_daily.loc[valid]

        borrowed = (exposure - 1.0).clip(lower=0.0)
        cash = (1.0 - exposure).clip(lower=0.0)
        gross = exposure * spy_ret - borrowed * (rf + FINANCING_SPREAD / 252.0) + cash * rf
        turnover = exposure.diff().abs().fillna(0.0)
        net = gross - turnover * COST_PER_TRADE
        return net, exposure

    # --------------------------------------------------------------- backtest
    def run_backtest(self, start_date: str, end_date: str, target_vol: float = TARGET_VOL,
                     max_leverage: float = MAX_LEVERAGE, initial_capital: float = 10000.0):
        try:
            ts_start, ts_end = pd.Timestamp(start_date), pd.Timestamp(end_date)
        except Exception:
            return {"error": "Invalid date format. Please use YYYY-MM-DD."}
        if ts_start >= ts_end:
            return {"error": "Start date must be before end date."}

        warnings = []
        t_lo, t_hi = TARGET_VOL_RANGE
        l_lo, l_hi = MAX_LEVERAGE_RANGE
        tv = min(max(float(target_vol), t_lo), t_hi)
        ml = min(max(float(max_leverage), l_lo), l_hi)
        if tv != target_vol:
            warnings.append(f"Target volatility capped to {tv:.0%} (allowed {t_lo:.0%}-{t_hi:.0%}).")
        if ml != max_leverage:
            warnings.append(f"Max leverage capped to {ml:.2f}x (allowed {l_lo:.1f}x-{l_hi:.1f}x).")

        net, exposure = self._simulate(tv, ml)
        net = net.loc[(net.index >= ts_start) & (net.index <= ts_end)]
        if len(net) < 30:
            return {"error": "Not enough data in that date range (need at least ~30 trading days)."}
        exposure = exposure.loc[net.index]
        spy_ret = self.spy_ret.loc[net.index]

        port_curve = (1 + net).cumprod() * initial_capital
        spy_curve = (1 + spy_ret).cumprod() * initial_capital
        df_res = pd.DataFrame({"Portfolio": port_curve, "SPY": spy_curve})

        year_end = df_res.resample("YE").last()
        start_row = pd.DataFrame({"Portfolio": initial_capital, "SPY": initial_capital},
                                 index=[df_res.index[0] - pd.Timedelta(days=1)])
        yearly = pd.concat([start_row, year_end]).pct_change().dropna()
        yearly_table = []
        for dt, row in yearly.iterrows():
            ex_year = exposure[exposure.index.year == dt.year]
            avg_ex = float(ex_year.mean()) if len(ex_year) else float("nan")
            yearly_table.append({
                "year": int(dt.year),
                "portfolio": float(row["Portfolio"]),
                "spy": float(row["SPY"]),
                "diff": float(row["Portfolio"] - row["SPY"]),
                "top_holdings": f"SPY avg {avg_ex:.2f}x" if np.isfinite(avg_ex) else "n/a",
            })

        rf_ann = float(self.rf_daily.reindex(net.index).mean() * 252)
        rets = df_res.pct_change().dropna()

        def _sharpe(col):
            vol = rets[col].std() * np.sqrt(252)
            if not np.isfinite(vol) or vol == 0:
                return 0.0
            v = (rets[col].mean() * 252 - rf_ann) / vol
            return float(v) if np.isfinite(v) else 0.0

        years = max((df_res.index[-1] - df_res.index[0]).days / 365.25, 1e-9)
        total_return = float(port_curve.iloc[-1] / initial_capital - 1)
        spy_total = float(spy_curve.iloc[-1] / initial_capital - 1)
        cagr = (1 + total_return) ** (1 / years) - 1
        spy_cagr = (1 + spy_total) ** (1 / years) - 1
        dd_p, dd_s = calc_max_drawdown(df_res["Portfolio"]), calc_max_drawdown(df_res["SPY"])
        sharpe_p, sharpe_s = _sharpe("Portfolio"), _sharpe("SPY")

        verb = "outperformed" if total_return >= spy_total else "underperformed"
        summary = (
            f"From {df_res.index[0].date()} to {df_res.index[-1].date()}, the growth strategy returned "
            f"{total_return:.1%} ({cagr:.1%}/yr) versus {spy_total:.1%} ({spy_cagr:.1%}/yr) for SPY - it {verb} "
            f"the benchmark by {abs(cagr - spy_cagr):.1%} per year. Sharpe {sharpe_p:.2f} (SPY {sharpe_s:.2f}), "
            f"max drawdown {dd_p:.1%} (SPY {dd_s:.1%}). Average exposure {exposure.mean():.2f}x, "
            f"above 1.0x on {float((exposure > 1.0).mean()):.0%} of days; uses leverage up to {ml:.2f}x."
        )

        # Exposure series (weekly sample) for the chart.
        exp_weekly = exposure.resample("W").last().dropna()

        return {
            "dates": [str(d.date()) for d in df_res.index],
            "portfolio": df_res["Portfolio"].tolist(),
            "spy": df_res["SPY"].tolist(),
            "exposure_dates": [str(d.date()) for d in exp_weekly.index],
            "exposure": [round(float(v), 3) for v in exp_weekly.values],
            "metrics": {
                "total_return": total_return,
                "spy_total_return": spy_total,
                "cagr": float(cagr),
                "spy_cagr": float(spy_cagr),
                "sharpe": sharpe_p,
                "spy_sharpe": sharpe_s,
                "max_dd": dd_p,
                "spy_max_dd": dd_s,
                "volatility": float(rets["Portfolio"].std() * np.sqrt(252)),
                "spy_volatility": float(rets["SPY"].std() * np.sqrt(252)),
                "risk_free": rf_ann,
                "avg_exposure": float(exposure.mean()),
                "pct_days_levered": float((exposure > 1.0).mean()),
            },
            "yearly_table": yearly_table,
            "summary": summary,
            "warnings": warnings,
        }

    # --------------------------------------------------------------- scenario
    def run_scenario(self, target_date: str = None, target_vol: float = TARGET_VOL,
                     max_leverage: float = MAX_LEVERAGE):
        spy_ret = self.spy_ret
        if target_date:
            try:
                spy_ret = spy_ret.loc[:pd.Timestamp(target_date)]
            except Exception:
                return {"error": "Invalid date format. Please use YYYY-MM-DD."}
        if len(spy_ret) < VOL_LOOKBACK + 5:
            return {"error": "Not enough data for that date."}

        tv = min(max(float(target_vol), TARGET_VOL_RANGE[0]), TARGET_VOL_RANGE[1])
        ml = min(max(float(max_leverage), MAX_LEVERAGE_RANGE[0]), MAX_LEVERAGE_RANGE[1])
        realized = spy_ret.rolling(VOL_LOOKBACK).std() * np.sqrt(252)
        target = (tv / realized).clip(0.0, ml)
        held = self._apply_band(target, REBALANCE_BAND)
        as_of = spy_ret.index[-1]
        rv = float(realized.iloc[-1])
        exposure = float(held.iloc[-1])
        rf_now = float(self.rf_ann.reindex(spy_ret.index).iloc[-1])

        regime = "calm" if rv < tv * 0.8 else ("normal" if rv <= tv * 1.25 else "turbulent")
        recent = held.dropna().iloc[-252:].iloc[::5]
        return {
            "date": str(as_of.date()),
            "exposure": {
                "target_exposure": exposure,
                "spy_weight": exposure,
                "cash_weight": max(1.0 - exposure, 0.0),
                "borrowed_weight": max(exposure - 1.0, 0.0),
                "realized_vol": rv,
                "target_vol": tv,
                "max_leverage": ml,
                "uncapped_exposure": float(tv / rv) if rv > 0 else None,
            },
            "regime": {"volatility": regime},
            "metrics": {"risk_free": rf_now},
            "exposure_history": {
                "dates": [str(d.date()) for d in recent.index],
                "values": [round(float(v), 3) for v in recent.values],
            },
        }
