import React from 'react';
import {
  Brain,
  Shield,
  Anchor,
  TrendingUp,
  Target,
  Layers,
  Activity,
  Clock,
  DollarSign,
  EyeOff
} from 'lucide-react';

export default function Info() {
  return (
    <div className="max-w-7xl mx-auto space-y-12 animate-fade-in pb-24">

      {/* HEADER */}
      <header className="text-center space-y-4 max-w-3xl mx-auto py-12 border-b border-slate-800">
        <h1 className="text-4xl md:text-5xl font-extrabold text-white">
          Hybrid <span className="text-blue-500">Asset Allocation</span> Framework
        </h1>
        <p className="text-lg text-slate-400">
          Combining Classical Financial Theory with Modern Machine Learning to create a robust, adaptive investment engine.
        </p>
      </header>

      {/* SECTION 1: PHILOSOPHY */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-900/30 rounded-lg border border-blue-700/50">
              <Anchor className="text-blue-400" size={32} />
            </div>
            <h2 className="text-2xl font-bold text-white">1. Anchor & Tilt Philosophy</h2>
          </div>
          <p className="text-slate-400 leading-relaxed">
            Most trading bots are unstable, flipping 100% between assets. We solve this using a two-step mathematical process:
          </p>
          <ul className="space-y-4">
            <li className="flex gap-3">
              <Shield className="text-green-400 shrink-0 mt-1" size={20} />
              <div>
                <strong className="text-white block">The Anchor (Safety)</strong>
                <span className="text-slate-500 text-sm">
                  We start with a "Market Equilibrium" portfolio based on <strong>Risk Parity</strong>. This asks:
                  <em>"If we know nothing, what is the safest, most diversified mix?"</em> This prevents the model from ever blowing up on a single bad bet.
                </span>
              </div>
            </li>
            <li className="flex gap-3">
              <Target className="text-purple-400 shrink-0 mt-1" size={20} />
              <div>
                <strong className="text-white block">The Tilt (Alpha)</strong>
                <span className="text-slate-500 text-sm">
                  We only deviate from safety when the AI identifies a high-confidence opportunity.
                  Using <strong>Black-Litterman</strong> math, we "tilt" the weights (e.g., +10% Tech) without abandoning the core diversification.
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
              <span className="text-slate-400">Step 1: Calculate Equilibrium</span>
              <span className="text-green-400">Stable Anchor</span>
            </div>
            <div className="flex justify-center text-slate-600">↓</div>
            <div className="flex justify-between p-3 bg-slate-900 rounded border border-slate-700/50">
              <span className="text-slate-400">Step 2: Generate AI Views</span>
              <span className="text-purple-400">Active Inputs</span>
            </div>
            <div className="flex justify-center text-slate-600">↓</div>
            <div className="flex justify-between p-3 bg-blue-900/20 rounded border border-blue-500/30">
              <span className="text-white font-bold">Final Portfolio</span>
              <span className="text-blue-400">Optimal Mix</span>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 2: THE BRAIN */}
      <div className="bg-slate-800 rounded-2xl border border-slate-700 p-8">
        <div className="flex items-center gap-3 mb-6">
          <Brain className="text-purple-400" size={32} />
          <h2 className="text-2xl font-bold text-white">2. The "Brain": ML & Regime Detection</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-700/50">
            <Activity className="text-orange-400 mb-3" size={24} />
            <h3 className="font-bold text-white mb-2">Regime Detection</h3>
            <p className="text-slate-400 text-sm">
              Scans market volatility. If the market is scared (High Vol), the model gets defensive. If calm (Low Vol), it takes calculated risks.
            </p>
          </div>
          <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-700/50">
            <TrendingUp className="text-blue-400 mb-3" size={24} />
            <h3 className="font-bold text-white mb-2">Momentum Scanner</h3>
            <p className="text-slate-400 text-sm">
              Identifies leading sectors by comparing 12-month performance vs SPY. It doesn't just chase winners; it measures the <em>strength</em> of the trend.
            </p>
          </div>
          <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-700/50">
            <Target className="text-green-400 mb-3" size={24} />
            <h3 className="font-bold text-white mb-2">Confidence Scoring</h3>
            <p className="text-slate-400 text-sm">
              A Logistic Regression model predicts the probability of a trend continuing. This "Probability" becomes the "Confidence" level for the trade.
            </p>
          </div>
        </div>
      </div>

      {/* SECTION 3: AVOIDING BIAS */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700">
          <div className="flex items-center gap-3 mb-6">
            <EyeOff className="text-red-400" size={32} />
            <h2 className="text-xl font-bold text-white">3. Anti-Bias Architecture</h2>
          </div>
          <p className="text-slate-400 mb-4 text-sm">
            We rigorously prevent "Look-Ahead Bias" (using tomorrow's data to trade today) using strict isolation protocols.
          </p>
          <ul className="space-y-3 text-sm">
            <li className="flex gap-2 items-start">
              <span className="text-green-400 font-mono">01.</span>
              <span className="text-slate-300">
                <strong>Strict Training Windows:</strong> Decisions for Date X are made using <em>only</em> the 504 days prior to X. The model literally cannot see the future.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <span className="text-green-400 font-mono">02.</span>
              <span className="text-slate-300">
                <strong>Walk-Forward Validation:</strong> We train on old data, make a prediction, and then simulate "walking forward" 3 months to see the result.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <span className="text-green-400 font-mono">03.</span>
              <span className="text-slate-300">
                <strong>Point-in-Time Features:</strong> Indicators like "Volatility" are calculated strictly using historical windows (e.g., <code>train_prices</code>), never the full dataset.
              </span>
            </li>
          </ul>
        </div>

        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700">
          <div className="flex items-center gap-3 mb-6">
            <Clock className="text-blue-400" size={32} />
            <h2 className="text-xl font-bold text-white">4. Real-World Realism</h2>
          </div>
          <p className="text-slate-400 mb-4 text-sm">
            Backtests often lie by ignoring fees and trading mechanics. We model the friction of the real world.
          </p>
          <ul className="space-y-3 text-sm">
            <li className="flex gap-2 items-start">
              <DollarSign className="text-yellow-400 shrink-0" size={16} />
              <span className="text-slate-300">
                <strong>Transaction Costs:</strong> We deduct <strong>0.05%</strong> fee on every trade. This proves high-turnover strategies usually lose money, while ours survives.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <Layers className="text-blue-400 shrink-0" size={16} />
              <span className="text-slate-300">
                <strong>The "Drift" Method:</strong> Between quarterly rebalances, we simulate <strong>Buy-and-Hold</strong>. If Tech doubles, it naturally grows in your portfolio. Other models assume "Daily Rebalancing" which kills momentum. Our method captures the true compound growth of winners.
              </span>
            </li>
          </ul>
        </div>
      </div>

    </div>
  );
}