import { useEffect, useState } from 'react';
import axios from 'axios';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';
import { TrendingUp, Gauge, AlertTriangle, RefreshCw, Calendar } from 'lucide-react';
import { API_BASE } from '../config';

const REGIME_STYLE = {
  calm: { label: 'Calm', cls: 'text-green-400 bg-green-500/10 border-green-500/30', note: 'Volatility is low, so the model is leaning in.' },
  normal: { label: 'Normal', cls: 'text-blue-400 bg-blue-500/10 border-blue-500/30', note: 'Volatility is near the target, so exposure is close to 1x.' },
  turbulent: { label: 'Turbulent', cls: 'text-red-400 bg-red-500/10 border-red-500/30', note: 'Volatility is high, so the model has cut exposure and holds cash.' },
};

const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;

export default function GrowthDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [targetVol, setTargetVol] = useState(0.20);
  const [maxLev, setMaxLev] = useState(1.5);
  const [asOf, setAsOf] = useState('');

  const fetchScenario = () =>
    axios
      .post(`${API_BASE}/growth/scenario`, { date: asOf || null, target_vol: targetVol, max_leverage: maxLev })
      .then((res) => { setData(res.data); setError(null); })
      .catch((err) => {
        console.error(err);
        const detail = err?.response?.data?.detail;
        setError(detail || 'Could not reach the engine. The server may be waking up from sleep (cold start can take ~60s). Please retry in a moment.');
      })
      .finally(() => setLoading(false));

  const run = () => {
    setLoading(true);
    fetchScenario();
  };

  // First load: `loading` already starts true, so only async callbacks set state here.
  useEffect(() => { fetchScenario(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const ex = data?.exposure;
  const regime = data ? REGIME_STYLE[data.regime.volatility] : null;
  const history = data ? data.exposure_history.dates.map((d, i) => ({ date: d, Exposure: data.exposure_history.values[i] })) : [];

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-fade-in pb-12">
      <header>
        <h1 className="text-3xl font-extrabold text-white">Growth <span className="text-green-500">Dashboard</span></h1>
        <p className="text-slate-400 mt-2">
          Volatility-managed exposure to the S&amp;P 500: more equity when markets are calm, less when they get rough.
        </p>
      </header>

      {/* CONTROLS */}
      <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
        <div>
          <label className="text-xs text-slate-400 font-bold flex justify-between mb-2">
            <span className="flex items-center gap-1"><Gauge size={14} /> Target volatility</span>
            <span className="text-white font-mono">{pct(targetVol)}</span>
          </label>
          <input type="range" min="0.10" max="0.30" step="0.01" value={targetVol} onChange={(e) => setTargetVol(parseFloat(e.target.value))} className="w-full accent-green-500" />
        </div>
        <div>
          <label className="text-xs text-slate-400 font-bold flex justify-between mb-2">
            <span className="flex items-center gap-1"><TrendingUp size={14} /> Max leverage</span>
            <span className="text-white font-mono">{maxLev.toFixed(2)}x</span>
          </label>
          <input type="range" min="1" max="2" step="0.05" value={maxLev} onChange={(e) => setMaxLev(parseFloat(e.target.value))} className="w-full accent-green-500" />
        </div>
        <div>
          <label className="text-xs text-slate-400 font-bold flex items-center gap-1 mb-2"><Calendar size={14} /> As of date (optional)</label>
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" />
        </div>
        <button onClick={run} disabled={loading} className="bg-green-600 hover:bg-green-500 disabled:opacity-60 text-white font-bold py-2.5 rounded-lg flex items-center justify-center gap-2 transition">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> {loading ? 'Calculating...' : 'Update'}
        </button>
      </div>

      {error && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3 text-sm text-amber-200">
          <AlertTriangle size={18} className="shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {data && (
        <div className="space-y-8">
          {/* HEADLINE */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 lg:col-span-1">
              <p className="text-xs text-slate-400 uppercase font-bold">Recommended exposure to SPY</p>
              <p className="text-6xl font-mono font-extrabold text-green-400 mt-2">{ex.target_exposure.toFixed(2)}x</p>
              <p className="text-xs text-slate-500 mt-2">As of {data.date}</p>
              <div className={`mt-4 inline-block px-3 py-1 rounded-full border text-xs font-bold ${regime.cls}`}>{regime.label} market</div>
              <p className="text-xs text-slate-400 mt-2">{regime.note}</p>
            </div>

            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 lg:col-span-2 space-y-5">
              <h3 className="font-bold text-white">Portfolio per $10,000</h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-slate-900/60 rounded-lg border border-slate-700/50 p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">In SPY</div>
                  <div className="text-white font-bold font-mono">${(ex.spy_weight * 10000).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                </div>
                <div className="bg-slate-900/60 rounded-lg border border-slate-700/50 p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Borrowed</div>
                  <div className="text-orange-400 font-bold font-mono">${(ex.borrowed_weight * 10000).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                </div>
                <div className="bg-slate-900/60 rounded-lg border border-slate-700/50 p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">In cash</div>
                  <div className="text-blue-400 font-bold font-mono">${(ex.cash_weight * 10000).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div><span className="text-slate-500 text-xs block">Realized vol (21d)</span><span className="font-mono text-white">{pct(ex.realized_vol, 1)}</span></div>
                <div><span className="text-slate-500 text-xs block">Target vol</span><span className="font-mono text-white">{pct(ex.target_vol, 0)}</span></div>
                <div><span className="text-slate-500 text-xs block">Exposure before cap</span><span className="font-mono text-white">{ex.uncapped_exposure != null ? `${ex.uncapped_exposure.toFixed(2)}x` : 'n/a'}</span></div>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Exposure = target volatility &divide; recent SPY volatility, capped at {ex.max_leverage.toFixed(2)}x. Anything above 1.0x
                is borrowed (margin or a leveraged ETF), which costs interest and amplifies losses as well as gains.
              </p>
            </div>
          </div>

          {/* EXPOSURE HISTORY */}
          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 h-[340px]">
            <h3 className="text-white font-bold mb-1">Exposure over the last year</h3>
            <p className="text-xs text-slate-500 mb-4">Above the dashed line the model is levered; below it, it is holding cash.</p>
            <ResponsiveContainer width="100%" height="78%">
              <AreaChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tickFormatter={(s) => s.substring(0, 7)} />
                <YAxis stroke="#94a3b8" domain={[0, Math.max(ex.max_leverage, 1)]} tickFormatter={(v) => `${v}x`} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} formatter={(v) => `${Number(v).toFixed(2)}x`} />
                <ReferenceLine y={1} stroke="#94a3b8" strokeDasharray="4 4" />
                <Area type="stepAfter" dataKey="Exposure" stroke="#4ade80" fill="#4ade80" fillOpacity={0.25} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <p className="text-center text-xs text-slate-600 max-w-2xl mx-auto">
        Illustrative only, not investment advice. Leverage can lose more than your initial investment. Past performance does not guarantee future results.
      </p>
    </div>
  );
}
