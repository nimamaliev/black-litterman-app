import { useState } from 'react';
import axios from 'axios';
import { API_BASE } from '../config';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from 'recharts';
import { Play, Calendar, Gauge, TrendingUp, AlertTriangle, Info } from 'lucide-react';

const pct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;

export default function GrowthBacktest() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [startDate, setStartDate] = useState('2006-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [targetVol, setTargetVol] = useState(0.20);
  const [maxLev, setMaxLev] = useState(1.5);

  const runBacktest = () => {
    setLoading(true);
    axios
      .post(`${API_BASE}/growth/backtest`, { start_date: startDate, end_date: endDate, target_vol: targetVol, max_leverage: maxLev })
      .then((res) => {
        const points = res.data.dates.map((date, i) => ({
          date,
          Growth: parseFloat(res.data.portfolio[i].toFixed(0)),
          SPY: parseFloat(res.data.spy[i].toFixed(0)),
        }));
        const exposure = res.data.exposure_dates.map((date, i) => ({ date, Exposure: res.data.exposure[i] }));
        setResult({ points, exposure, ...res.data });
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        const detail = err?.response?.data?.detail;
        alert(detail ? `Backtest error: ${detail}` : 'Error running backtest. The server may be waking up; please retry in a minute.');
        setLoading(false);
      });
  };

  const ddPoints = result
    ? (() => {
        let gMax = -Infinity, sMax = -Infinity;
        return result.points.map((pt) => {
          gMax = Math.max(gMax, pt.Growth);
          sMax = Math.max(sMax, pt.SPY);
          return { date: pt.date, Growth: +((pt.Growth / gMax - 1) * 100).toFixed(2), SPY: +((pt.SPY / sMax - 1) * 100).toFixed(2) };
        });
      })()
    : [];

  const m = result?.metrics;
  const tooltipStyle = { backgroundColor: '#0f172a', borderColor: '#334155' };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-fade-in pb-12">
      <header>
        <h1 className="text-3xl font-extrabold text-white">Growth <span className="text-green-500">Backtest Engine</span></h1>
        <p className="text-slate-400 mt-2">Replay the volatility-managed strategy against buy-and-hold SPY. Borrowing costs and trading costs are included.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-4">
          <h3 className="font-bold text-white flex items-center gap-2"><Calendar size={18} className="text-green-400" /> Simulation Period</h3>
          <div className="flex flex-col gap-2">
            <input type="date" className="bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            <input type="date" className="bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
        </div>

        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-5 lg:col-span-2">
          <h3 className="font-bold text-white">Risk Settings</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="text-xs text-slate-400 font-bold flex justify-between mb-2">
                <span className="flex items-center gap-1"><Gauge size={14} /> Target volatility</span>
                <span className="text-white font-mono">{pct(targetVol, 0)}</span>
              </label>
              <input type="range" min="0.10" max="0.30" step="0.01" value={targetVol} onChange={(e) => setTargetVol(parseFloat(e.target.value))} className="w-full accent-green-500" />
              <p className="text-[10px] text-slate-500 mt-1">SPY itself has run at roughly 19% a year.</p>
            </div>
            <div>
              <label className="text-xs text-slate-400 font-bold flex justify-between mb-2">
                <span className="flex items-center gap-1"><TrendingUp size={14} /> Max leverage</span>
                <span className="text-white font-mono">{maxLev.toFixed(2)}x</span>
              </label>
              <input type="range" min="1" max="2" step="0.05" value={maxLev} onChange={(e) => setMaxLev(parseFloat(e.target.value))} className="w-full accent-green-500" />
              <p className="text-[10px] text-slate-500 mt-1">1.00x means no borrowing at all.</p>
            </div>
          </div>
        </div>
      </div>

      <button onClick={runBacktest} disabled={loading} className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-60 text-white font-bold py-4 rounded-xl shadow-lg flex items-center justify-center gap-3 transition">
        {loading ? 'Running Simulation...' : <><Play size={20} /> Run Growth Backtest</>}
      </button>

      {result && (
        <div className="space-y-8 animate-fade-in">
          {result.summary && (
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 flex items-start gap-3">
              <Info size={18} className="text-green-400 shrink-0 mt-0.5" />
              <p className="text-sm text-slate-300 leading-relaxed">{result.summary}</p>
            </div>
          )}
          {result.warnings?.length > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 space-y-1">
              <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase"><AlertTriangle size={14} /> Input adjustments</div>
              <ul className="text-xs text-amber-200/90 list-disc list-inside space-y-0.5">
                {result.warnings.map((w, idx) => <li key={idx}>{w}</li>)}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">CAGR</p>
              <p className={`text-2xl font-mono font-bold ${m.cagr >= m.spy_cagr ? 'text-green-400' : 'text-white'}`}>{pct(m.cagr)}</p>
              <p className="text-[10px] text-slate-500">SPY: {pct(m.spy_cagr)}</p>
            </div>
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Total Return</p>
              <p className="text-2xl font-mono font-bold text-white">{pct(m.total_return, 0)}</p>
              <p className="text-[10px] text-slate-500">SPY: {pct(m.spy_total_return, 0)}</p>
            </div>
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Sharpe Ratio</p>
              <p className="text-2xl font-mono font-bold text-blue-400">{m.sharpe.toFixed(2)}</p>
              <p className="text-[10px] text-slate-500">SPY: {m.spy_sharpe.toFixed(2)}</p>
            </div>
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Max Drawdown</p>
              <p className="text-2xl font-mono font-bold text-red-400">{pct(m.max_dd)}</p>
              <p className="text-[10px] text-slate-500">SPY: {pct(m.spy_max_dd)}</p>
            </div>
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Avg Exposure</p>
              <p className="text-2xl font-mono font-bold text-orange-400">{m.avg_exposure.toFixed(2)}x</p>
              <p className="text-[10px] text-slate-500">Levered {pct(m.pct_days_levered, 0)} of days</p>
            </div>
          </div>

          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 h-[400px]">
            <h3 className="text-white font-bold mb-4">Wealth Growth ($10k Initial)</h3>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={result.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tickFormatter={(s) => s.substring(0, 4)} />
                <YAxis stroke="#94a3b8" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => `$${v.toLocaleString()}`} />
                <Legend />
                <Line type="monotone" dataKey="Growth" stroke="#4ade80" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="SPY" stroke="#64748b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 h-[300px]">
            <h3 className="text-white font-bold mb-1">Drawdown</h3>
            <p className="text-xs text-slate-500 mb-4">How far each strategy fell below its own previous peak (%). Closer to 0 is better.</p>
            <ResponsiveContainer width="100%" height="80%">
              <AreaChart data={ddPoints}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tickFormatter={(s) => s.substring(0, 4)} />
                <YAxis stroke="#94a3b8" tickFormatter={(v) => `${v}%`} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
                <Legend />
                <Area type="monotone" dataKey="Growth" stroke="#f87171" fill="#f87171" fillOpacity={0.25} />
                <Area type="monotone" dataKey="SPY" stroke="#64748b" fill="#64748b" fillOpacity={0.15} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 h-[280px]">
            <h3 className="text-white font-bold mb-1">Exposure to SPY</h3>
            <p className="text-xs text-slate-500 mb-4">Weekly. The model sits above 1x in calm markets and drops toward cash when volatility spikes.</p>
            <ResponsiveContainer width="100%" height="78%">
              <AreaChart data={result.exposure}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tickFormatter={(s) => s.substring(0, 4)} />
                <YAxis stroke="#94a3b8" domain={[0, 'dataMax']} tickFormatter={(v) => `${v}x`} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${Number(v).toFixed(2)}x`} />
                <ReferenceLine y={1} stroke="#94a3b8" strokeDasharray="4 4" />
                <Area type="stepAfter" dataKey="Exposure" stroke="#4ade80" fill="#4ade80" fillOpacity={0.25} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
            <div className="p-4 border-b border-slate-700 font-bold text-white">Yearly Performance</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left text-slate-300">
                <thead className="text-xs text-slate-400 uppercase bg-slate-900/50">
                  <tr>
                    <th className="px-6 py-3">Year</th>
                    <th className="px-6 py-3">Growth</th>
                    <th className="px-6 py-3">SPY</th>
                    <th className="px-6 py-3">Excess</th>
                    <th className="px-6 py-3">Avg Exposure</th>
                  </tr>
                </thead>
                <tbody>
                  {result.yearly_table.map((row) => (
                    <tr key={row.year} className="border-b border-slate-700 hover:bg-slate-700/50">
                      <td className="px-6 py-4 font-mono">{row.year}</td>
                      <td className={`px-6 py-4 font-bold ${row.portfolio > 0 ? 'text-green-400' : 'text-red-400'}`}>{pct(row.portfolio)}</td>
                      <td className="px-6 py-4">{pct(row.spy)}</td>
                      <td className={`px-6 py-4 font-bold ${row.diff > 0 ? 'text-blue-400' : 'text-slate-500'}`}>{row.diff > 0 ? '+' : ''}{pct(row.diff)}</td>
                      <td className="px-6 py-4 text-xs font-mono text-slate-400">{row.top_holdings}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
