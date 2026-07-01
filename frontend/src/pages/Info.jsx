import React from 'react';
import {
  Shield,
  Anchor,
  Activity,
  Gauge,
  Target,
  Layers,
  Clock,
  DollarSign,
  EyeOff,
  TrendingDown,
} from 'lucide-react';

export default function Info() {
  return (
    <div className="max-w-7xl mx-auto space-y-12 animate-fade-in pb-24">

      {/* HEADER */}
      <header className="text-center space-y-4 max-w-3xl mx-auto py-12 border-b border-slate-800">
        <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-blue-400 bg-blue-500/10 px-3 py-1 rounded-full">
          <Shield size={14} /> Defensive Strategy
        </div>
        <h1 className="text-4xl md:text-5xl font-extrabold text-white">
          A <span className="text-blue-500">Crash-Protection</span> Allocation Model
        </h1>
        <p className="text-lg text-slate-400">
          A sector-rotation Black-Litterman portfolio with a volatility-targeting overlay. Its single
          job: stay invested in calm markets, and pull risk off the table before drawdowns get deep.
        </p>
      </header>

      {/* SECTION 1: PHILOSOPHY */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-900/30 rounded-lg border border-blue-700/50">
              <Anchor className="text-blue-400" size={32} />
            </div>
            <h2 className="text-2xl font-bold text-white">1. Anchor, Tilt &amp; De-risk</h2>
          </div>
          <p className="text-slate-400 leading-relaxed">
            The portfolio is built in three deliberate layers, each one designed to limit how much can go wrong:
          </p>
          <ul className="space-y-4">
            <li className="flex gap-3">
              <Shield className="text-green-400 shrink-0 mt-1" size={20} />
              <div>
                <strong className="text-white block">The Anchor (Diversify)</strong>
                <span className="text-slate-500 text-sm">
                  We start from a risk-based <strong>inverse-volatility</strong> equilibrium across the 11 sector ETFs.
                  This is the &quot;if we knew nothing&quot; portfolio &mdash; broadly diversified, never concentrated in a single bet.
                </span>
              </div>
            </li>
            <li className="flex gap-3">
              <Target className="text-purple-400 shrink-0 mt-1" size={20} />
              <div>
                <strong className="text-white block">The Tilt (Adapt)</strong>
                <span className="text-slate-500 text-sm">
                  Using <strong>Black-Litterman</strong> math we apply only modest, high-confidence tilts toward stronger sectors &mdash;
                  enough to adapt to the regime, never enough to bet the whole portfolio on one view.
                </span>
              </div>
            </li>
            <li className="flex gap-3">
              <TrendingDown className="text-red-400 shrink-0 mt-1" size={20} />
              <div>
                <strong className="text-white block">The De-risk (Protect)</strong>
                <span className="text-slate-500 text-sm">
                  A <strong>volatility-targeting overlay</strong> scales total equity exposure to hold risk near a 10% annual target.
                  When markets turn turbulent it moves money into cash &mdash; this is what caps the drawdowns.
                </span>
              </div>
            </li>
          </ul>
        </div>
        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <Layers size={120} />
          </div>
          <h3 className="text-white font-bold mb-4">Allocation Logic</h3>
          <div className="space-y-2 font-mono text-sm">
            <div className="flex justify-between p-3 bg-slate-900 rounded border border-slate-700/50">
              <span className="text-slate-400">1. Risk-based anchor</span>
              <span className="text-green-400">Diversified</span>
            </div>
            <div className="flex justify-center text-slate-600">\u2193</div>
            <div className="flex justify-between p-3 bg-slate-900 rounded border border-slate-700/50">
              <span className="text-slate-400">2. Modest BL tilts</span>
              <span className="text-purple-400">Adaptive</span>
            </div>
            <div className="flex justify-center text-slate-600">\u2193</div>
            <div className="flex justify-between p-3 bg-slate-900 rounded border border-slate-700/50">
              <span className="text-slate-400">3. Volatility target</span>
              <span className="text-red-400">De-risk to cash</span>
            </div>
            <div className="flex justify-center text-slate-600">\u2193</div>
            <div className="flex justify-between p-3 bg-blue-900/20 rounded border border-blue-500/30">
              <span className="text-white font-bold">Final Portfolio</span>
              <span className="text-blue-400">Risk-controlled</span>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 2: THE DEFENSE ENGINE */}
      <div className="bg-slate-800 rounded-2xl border border-slate-700 p-8">
        <div className="flex items-center gap-3 mb-6">
          <Gauge className="text-purple-400" size={32} />
          <h2 className="text-2xl font-bold text-white">2. The Defense Engine</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-700/50">
            <Activity className="text-orange-400 mb-3" size={24} />
            <h3 className="font-bold text-white mb-2">Regime Detection</h3>
            <p className="text-slate-400 text-sm">
              The model continuously reads market volatility. In calm regimes it stays invested; when fear spikes it shifts to a defensive posture.
            </p>
          </div>
          <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-700/50">
            <Gauge className="text-blue-400 mb-3" size={24} />
            <h3 className="font-bold text-white mb-2">Volatility Targeting</h3>
            <p className="text-slate-400 text-sm">
              Exposure is scaled to hold portfolio risk near a 10% annual target. As realized volatility rises, equity exposure is automatically cut &mdash; sometimes well below fully invested.
            </p>
          </div>
          <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-700/50">
            <Shield className="text-green-400 mb-3" size={24} />
            <h3 className="font-bold text-white mb-2">Cash as a Position</h3>
            <p className="text-slate-400 text-sm">
              Whatever is not invested in equities sits in cash, earning the risk-free rate. Holding cash through storms is the core of how this model protects capital.
            </p>
          </div>
        </div>
      </div>

      {/* SECTION 3: WHAT THE DEFENSE BUYS YOU */}
      <div className="bg-gradient-to-br from-blue-900/20 to-slate-800 rounded-2xl border border-blue-500/20 p-8">
        <div className="flex items-center gap-3 mb-2">
          <Shield className="text-blue-400" size={32} />
          <h2 className="text-2xl font-bold text-white">3. What the Defense Buys You</h2>
        </div>
        <p className="text-slate-400 text-sm mb-6 max-w-2xl">
          Across a 2007&ndash;2026 walk-forward backtest, the volatility-targeted model gave up a little raw
          return in exchange for dramatically smaller losses &mdash; exactly the trade a defensive investor wants.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-white font-mono">0.70</div>
            <div className="text-xs text-slate-500 mt-1">Sharpe Ratio</div>
            <div className="text-[11px] text-green-400 mt-1">vs 0.52 buy &amp; hold</div>
          </div>
          <div className="bg-slate-900/60 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-white font-mono">-15%</div>
            <div className="text-xs text-slate-500 mt-1">Max Drawdown</div>
            <div className="text-[11px] text-green-400 mt-1">vs -53% buy &amp; hold</div>
          </div>
          <div className="bg-slate-900/60 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-white font-mono">-12%</div>
            <div className="text-xs text-slate-500 mt-1">2008 Crisis</div>
            <div className="text-[11px] text-green-400 mt-1">vs ~-55% market</div>
          </div>
          <div className="bg-slate-900/60 rounded-xl border border-slate-700/50 p-4 text-center">
            <div className="text-3xl font-bold text-white font-mono">-11%</div>
            <div className="text-xs text-slate-500 mt-1">2020 COVID Crash</div>
            <div className="text-[11px] text-green-400 mt-1">vs ~-34% market</div>
          </div>
        </div>
        <p className="text-[11px] text-slate-600 mt-4">
          Backtested on US sector ETFs, net of 0.05% per-trade costs. Illustrative only; past performance does not guarantee future results.
        </p>
      </div>

      {/* SECTION 4: AVOIDING BIAS */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700">
          <div className="flex items-center gap-3 mb-6">
            <EyeOff className="text-red-400" size={32} />
            <h2 className="text-xl font-bold text-white">4. Anti-Bias Architecture</h2>
          </div>
          <p className="text-slate-400 mb-4 text-sm">
            The backtest rigorously prevents &quot;look-ahead bias&quot; (using tomorrow&apos;s data to trade today) through strict isolation protocols.
          </p>
          <ul className="space-y-3 text-sm">
            <li className="flex gap-2 items-start">
              <span className="text-green-400 font-mono">01.</span>
              <span className="text-slate-300">
                <strong>Strict Training Windows:</strong> Decisions for date X use <em>only</em> the 504 days prior to X. The model literally cannot see the future.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <span className="text-green-400 font-mono">02.</span>
              <span className="text-slate-300">
                <strong>Walk-Forward Validation:</strong> We train on past data, make a decision, then step forward in time to measure the real result.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <span className="text-green-400 font-mono">03.</span>
              <span className="text-slate-300">
                <strong>Point-in-Time Features:</strong> Risk signals like volatility are computed strictly from historical windows, never the full dataset.
              </span>
            </li>
          </ul>
        </div>

        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700">
          <div className="flex items-center gap-3 mb-6">
            <Clock className="text-blue-400" size={32} />
            <h2 className="text-xl font-bold text-white">5. Real-World Realism</h2>
          </div>
          <p className="text-slate-400 mb-4 text-sm">
            Backtests often flatter themselves by ignoring fees and trading mechanics. This one models the friction of the real world.
          </p>
          <ul className="space-y-3 text-sm">
            <li className="flex gap-2 items-start">
              <DollarSign className="text-yellow-400 shrink-0" size={16} />
              <span className="text-slate-300">
                <strong>Transaction Costs:</strong> A <strong>0.05%</strong> fee is deducted on every trade, so the results reflect what survives real-world churn.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <Layers className="text-blue-400 shrink-0" size={16} />
              <span className="text-slate-300">
                <strong>The &quot;Drift&quot; Method:</strong> Between quarterly rebalances the portfolio is held, not reset daily &mdash; capturing realistic compounding instead of an idealized daily rebalance.
              </span>
            </li>
          </ul>
        </div>
      </div>

    </div>
  );
}
