import { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE } from '../config';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Radio, Info, AlertTriangle } from 'lucide-react';

const pct = (v) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`);

export default function TrackRecord() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${API_BASE}/track_record`)
      .then(res => setData(res.data))
      .catch(() => setError("Could not reach the engine. It may be waking up (cold start ~60s); refresh in a moment."));
  }, []);

  const points = data && data.dates
    ? data.dates.map((date, i) => ({ date, Model: +data.portfolio[i].toFixed(0), SPY: +data.spy[i].toFixed(0) }))
    : [];
  const recent = data && data.records ? [...data.records].reverse().slice(0, 10) : [];

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-fade-in pb-12">
      <header>
        <h1 className="text-3xl font-extrabold text-white">Live <span className="text-blue-500">Track Record</span></h1>
        <p className="text-slate-400 mt-2 max-w-3xl">
          Every weekday after the US close, the model&apos;s recommendation is written to an append-only log in the
          public GitHub repository (the <code className="text-slate-300">track-record</code> branch), so every entry is
          timestamped by git and can&apos;t be quietly revised. Performance here is measured only going forward from each entry.
        </p>
      </header>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-200 flex gap-2">
          <AlertTriangle size={18} className="shrink-0" /> {error}
        </div>
      )}
      {!data && !error && <p className="text-blue-400 font-mono animate-pulse">Loading track record...</p>}

      {data && data.message && (
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 flex items-start gap-3">
          <Info size={18} className="text-blue-400 shrink-0 mt-0.5" />
          <p className="text-sm text-slate-300">{data.message}</p>
        </div>
      )}

      {data && data.metrics && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ['Total Return', pct(data.metrics.total_return), `SPY: ${pct(data.spy_metrics.total_return)}`],
              ['Sharpe', data.metrics.sharpe.toFixed(2), `SPY: ${data.spy_metrics.sharpe.toFixed(2)}`],
              ['Max Drawdown', pct(data.metrics.max_dd), `SPY: ${pct(data.spy_metrics.max_dd)}`],
              ['Live Since', data.first_record, `${data.trading_days} trading days`],
            ].map(([label, value, sub]) => (
              <div key={label} className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <p className="text-xs text-slate-400 uppercase font-bold">{label}</p>
                <p className="text-2xl font-mono font-bold text-white">{value}</p>
                <p className="text-[10px] text-slate-500">{sub}</p>
              </div>
            ))}
          </div>

          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 h-[360px]">
            <h3 className="text-white font-bold mb-4 flex items-center gap-2"><Radio size={16} className="text-red-400" /> Live Performance ($10k)</h3>
            <ResponsiveContainer width="100%" height="85%">
              <LineChart data={points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" domain={['auto', 'auto']} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} />
                <Tooltip contentStyle={ { backgroundColor: '#0f172a', borderColor: '#334155' } } formatter={(v) => `$${v.toLocaleString()}`} />
                <Legend />
                <Line type="monotone" dataKey="Model" stroke="#2dd4bf" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="SPY" stroke="#64748b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {recent.length > 0 && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-x-auto">
          <div className="p-4 border-b border-slate-700 font-bold text-white">Latest Recorded Recommendations</div>
          <table className="w-full text-sm text-left text-slate-300">
            <thead className="text-xs text-slate-400 uppercase bg-slate-900/50">
              <tr>
                <th className="px-4 py-3">Data Date</th>
                <th className="px-4 py-3">Invested</th>
                <th className="px-4 py-3">Top Holdings</th>
              </tr>
            </thead>
            <tbody>
              {recent.map(r => (
                <tr key={r.data_date} className="border-b border-slate-700">
                  <td className="px-4 py-3 font-mono">{r.data_date}</td>
                  <td className="px-4 py-3 font-mono">{pct(r.invested)}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">
                    {Object.entries(r.weights).sort((a, b) => b[1] - a[1]).slice(0, 4)
                      .map(([t, w]) => `${t} ${(w * 100).toFixed(0)}%`).join(' · ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
