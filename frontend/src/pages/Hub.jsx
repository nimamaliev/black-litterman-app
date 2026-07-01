import { Link } from 'react-router-dom';
import { Shield, TrendingUp, Scale, ArrowRight, Lock } from 'lucide-react';

// Visual accent per strategy. Class strings are written out in full so
// Tailwind's compiler keeps them (no dynamic class construction).
const ACCENT = {
  blue: { border: 'hover:border-blue-500/60', icon: 'bg-blue-500/20 text-blue-400', chip: 'text-blue-300', btn: 'bg-blue-600 hover:bg-blue-500' },
  green: { border: 'hover:border-green-500/60', icon: 'bg-green-500/20 text-green-400', chip: 'text-green-300', btn: 'bg-green-600 hover:bg-green-500' },
  purple: { border: 'hover:border-purple-500/60', icon: 'bg-purple-500/20 text-purple-400', chip: 'text-purple-300', btn: 'bg-purple-600 hover:bg-purple-500' },
};

// The strategy catalog. Add future models here as their own entries.
const STRATEGIES = [
  {
    key: 'defensive',
    name: 'Defensive',
    subtitle: 'Crash Protection',
    status: 'live',
    to: '/defensive',
    accent: 'blue',
    icon: Shield,
    blurb:
      'A sector-rotation Black-Litterman model with a volatility-targeting overlay that scales out of equities into cash when markets turn turbulent. Engineered to lose far less when it matters most.',
    bestFor: 'Recessions \u00b7 bear markets \u00b7 high-volatility regimes',
    metrics: [
      { label: 'Sharpe', value: '0.70' },
      { label: 'Max Drawdown', value: '-15%' },
      { label: 'CAGR', value: '8.6%' },
      { label: 'GFC 2008', value: '-12%' },
    ],
  },
  {
    key: 'growth',
    name: 'Growth',
    subtitle: 'Bull Market',
    status: 'soon',
    accent: 'green',
    icon: TrendingUp,
    blurb:
      'An offense-oriented allocation built to capture upside in trending, low-volatility markets. Currently in development.',
    bestFor: 'Expansions \u00b7 bull markets \u00b7 risk-on regimes',
    metrics: [],
  },
  {
    key: 'balanced',
    name: 'Balanced',
    subtitle: 'All-Weather',
    status: 'soon',
    accent: 'purple',
    icon: Scale,
    blurb:
      'A steady, diversified blend aiming for smooth compounding across every market regime. Currently in development.',
    bestFor: 'Long-term \u00b7 hands-off investors',
    metrics: [],
  },
];

function StrategyCard({ s }) {
  const a = ACCENT[s.accent];
  const Icon = s.icon;
  const live = s.status === 'live';

  return (
    <div className={`bg-slate-800 rounded-2xl border border-slate-700 p-6 flex flex-col transition duration-300 ${live ? a.border : 'opacity-70'}`}>
      <div className="flex items-start justify-between mb-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${a.icon}`}>
          <Icon size={24} />
        </div>
        {live ? (
          <span className="text-[10px] font-bold uppercase tracking-wider text-green-400 bg-green-500/10 px-2 py-1 rounded-full">Live</span>
        ) : (
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-700/50 px-2 py-1 rounded-full flex items-center gap-1"><Lock size={10} /> Soon</span>
        )}
      </div>

      <h3 className="text-xl font-bold text-white">{s.name}</h3>
      <p className={`text-sm font-medium mb-3 ${a.chip}`}>{s.subtitle}</p>
      <p className="text-slate-400 text-sm leading-relaxed mb-4 flex-grow">{s.blurb}</p>

      {s.metrics.length > 0 && (
        <div className="grid grid-cols-2 gap-2 mb-4">
          {s.metrics.map((m) => (
            <div key={m.label} className="bg-slate-900/60 rounded-lg border border-slate-700/50 px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">{m.label}</div>
              <div className="text-white font-bold font-mono text-sm">{m.value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="text-xs text-slate-500 mb-5">
        <span className="font-semibold text-slate-400">Best for: </span>{s.bestFor}
      </div>

      {live ? (
        <Link to={s.to} className={`mt-auto ${a.btn} text-white font-bold text-sm px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 transition`}>
          Open Strategy <ArrowRight size={16} />
        </Link>
      ) : (
        <button disabled className="mt-auto bg-slate-700/50 text-slate-500 font-bold text-sm px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 cursor-not-allowed">
          Coming Soon
        </button>
      )}
    </div>
  );
}

export default function Hub() {
  return (
    <div className="max-w-7xl mx-auto space-y-10 animate-fade-in pb-16">
      <header className="text-center space-y-4 max-w-3xl mx-auto py-10 border-b border-slate-800">
        <h1 className="text-4xl md:text-5xl font-extrabold text-white">
          The <span className="text-blue-500">Strategy</span> Library
        </h1>
        <p className="text-lg text-slate-400">
          Each model is built for a different market environment. Pick the one that fits your
          view \u2014 protect capital in a downturn, or chase growth in a boom.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {STRATEGIES.map((s) => (
          <StrategyCard key={s.key} s={s} />
        ))}
      </div>

      <p className="text-center text-xs text-slate-600 max-w-2xl mx-auto">
        Metrics are from a walk-forward backtest of US sector ETFs (2007\u20132026) and are
        illustrative only. Past performance does not guarantee future results.
      </p>
    </div>
  );
}
