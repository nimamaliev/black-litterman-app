import { useState } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Play, Activity, Calendar, Plus, TrendingUp, AlertTriangle, HelpCircle } from 'lucide-react';

const SECTOR_MAP = Object.keys({'XLK':1,'XLF':1,'XLE':1,'XLV':1,'XLI':1,'XLC':1,'XLP':1,'XLU':1,'XLY':1,'XLB':1,'XLRE':1});

export default function Backtest() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  // Period Config
  const [startDate, setStartDate] = useState("2006-01-01");
  const [endDate, setEndDate] = useState("2026-01-06");

  // View Config
  const [views, setViews] = useState([]);
  const [newView, setNewView] = useState({
    ticker: 'XLK',
    value: 0.05,
    confidence: 0.50,
    start_date: "",  // New
    end_date: ""     // New
  });

  const addView = () => {
    // Basic validation
    if (newView.start_date && newView.end_date && newView.start_date > newView.end_date) {
        alert("Start date must be before end date");
        return;
    }
    setViews([...views, { ...newView }]);
  };

  const removeView = (i) => {
    const u = [...views]; u.splice(i, 1); setViews(u);
  };

  const runBacktest = () => {
    setLoading(true);
    axios.post('https://blai-dwb1.onrender.com/simulation/backtest', {
      start_date: startDate,
      end_date: endDate,
      views: views
    })
    .then(res => {
      // --- DEBUG LINE: Check if 'top_holdings' exists in the response ---
      console.log("Backtest Data Received:", res.data.yearly_table); 
      // ------------------------------------------------------------------
      const points = res.data.dates.map((date, i) => ({
        date,
        Portfolio: parseFloat(res.data.portfolio[i].toFixed(0)),
        SPY: parseFloat(res.data.spy[i].toFixed(0))
      }));
      setResult({ points, ...res.data });
      setLoading(false);
    })
    .catch(err => {
      console.error(err);
      alert("Error running backtest.");
      setLoading(false);
    });
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-fade-in pb-12">
      <header>
        <h1 className="text-3xl font-extrabold text-white">Historical <span className="text-blue-500">Backtest Engine</span></h1>
        <p className="text-slate-400 mt-2">Simulate performance vs SPY with detailed metrics.</p>
      </header>

      {/* CONFIG */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* GLOBAL PERIOD */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-4">
          <h3 className="font-bold text-white flex items-center gap-2"><Calendar size={18} className="text-blue-400"/> Simulation Period</h3>
          <div className="flex flex-col gap-2">
             <input type="date" className="bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" value={startDate} onChange={e => setStartDate(e.target.value)} />
             <input type="date" className="bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" value={endDate} onChange={e => setEndDate(e.target.value)} />
          </div>
        </div>

        {/* VIEWS BUILDER */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-4 lg:col-span-2">
          <h3 className="font-bold text-white flex items-center gap-2"><Activity size={18} className="text-purple-400"/> Discretionary Views</h3>

          <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end bg-slate-900/50 p-3 rounded-lg border border-slate-700">
             <div className="col-span-1">
               <label className="text-[10px] text-slate-500 font-bold block mb-1">Ticker</label>
               <select className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" value={newView.ticker} onChange={e => setNewView({...newView, ticker: e.target.value})}>
                 {SECTOR_MAP.map(t => <option key={t}>{t}</option>)}
               </select>
             </div>
             <div className="col-span-1">
               <label className="text-[10px] text-slate-500 font-bold block mb-1">Excess</label>
               <input type="number" step="0.01" className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" value={newView.value} onChange={e => setNewView({...newView, value: parseFloat(e.target.value)})}/>
             </div>
             <div className="col-span-1">
               <label className="text-[10px] text-slate-500 font-bold flex items-center gap-1 mb-1">Conf <HelpCircle size={8}/></label>
               <input type="number" step="0.1" className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white text-sm" value={newView.confidence} onChange={e => setNewView({...newView, confidence: parseFloat(e.target.value)})}/>
             </div>
             <div className="col-span-1">
                <label className="text-[10px] text-slate-500 font-bold block mb-1">Start (Opt)</label>
                <input type="date" className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white text-xs" value={newView.start_date} onChange={e => setNewView({...newView, start_date: e.target.value})}/>
             </div>
             <div className="col-span-1">
                <label className="text-[10px] text-slate-500 font-bold block mb-1">End (Opt)</label>
                <input type="date" className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white text-xs" value={newView.end_date} onChange={e => setNewView({...newView, end_date: e.target.value})}/>
             </div>
             <div className="col-span-1">
               <button onClick={addView} className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold p-2 rounded flex items-center justify-center"><Plus size={18}/></button>
             </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {views.map((v, i) => (
              <span key={i} className="bg-slate-900 border border-slate-700 px-3 py-1 rounded-full text-xs text-white flex items-center gap-2">
                <span className="font-bold text-blue-400">{v.ticker}</span>
                <span>{(v.value > 0 ? "+" : "")}{(v.value*100).toFixed(0)}%</span>
                <span className="text-slate-500 text-[10px]">
                   ({(v.confidence * 100).toFixed(0)}% conf)
                   {v.start_date ? ` [${v.start_date.substring(0,4)}-${v.end_date ? v.end_date.substring(0,4) : 'Now'}]` : ''}
                </span>
                <button onClick={() => removeView(i)} className="text-slate-500 hover:text-red-400 ml-1">×</button>
              </span>
            ))}
            {views.length === 0 && <span className="text-xs text-slate-500 italic p-2">No active views. Running Baseline Model.</span>}
          </div>
        </div>
      </div>

      <button onClick={runBacktest} disabled={loading} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-4 rounded-xl shadow-lg flex items-center justify-center gap-3 transition">
        {loading ? "Running Simulation..." : <><Play size={20} /> Run Backtest Engine</>}
      </button>

      {/* RESULTS */}
      {result && (
        <div className="space-y-8 animate-fade-in">
          {/* METRICS GRID */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Total Return</p>
              <p className={`text-2xl font-mono font-bold ${result.metrics.total_return >= result.metrics.spy_total_return ? "text-green-400" : "text-white"}`}>{(result.metrics.total_return * 100).toFixed(1)}%</p>
              <p className="text-[10px] text-slate-500">SPY: {(result.metrics.spy_total_return * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Sharpe Ratio</p>
              <p className="text-2xl font-mono font-bold text-blue-400">{result.metrics.sharpe.toFixed(2)}</p>
              <p className="text-[10px] text-slate-500">SPY: {result.metrics.spy_sharpe.toFixed(2)}</p>
            </div>
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Max Drawdown</p>
              <p className="text-2xl font-mono font-bold text-red-400">{(result.metrics.max_dd * 100).toFixed(1)}%</p>
              <p className="text-[10px] text-slate-500">SPY: {(result.metrics.spy_max_dd * 100).toFixed(1)}%</p>
            </div>
             <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-bold">Volatility</p>
              <p className="text-2xl font-mono font-bold text-orange-400">{(result.metrics.volatility * 100).toFixed(1)}%</p>
              <p className="text-[10px] text-slate-500">SPY: {(result.metrics.spy_volatility * 100).toFixed(1)}%</p>
            </div>
          </div>

          {/* CHART */}
          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 h-[400px]">
            <h3 className="text-white font-bold mb-4">Wealth Growth ($10k Initial)</h3>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={result.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tickFormatter={(s)=>s.substring(0,4)}/>
                <YAxis stroke="#94a3b8" tickFormatter={(v)=>`$${v/1000}k`}/>
                <Tooltip contentStyle={{backgroundColor:'#0f172a', borderColor:'#334155'}} formatter={(v)=>`$${v.toLocaleString()}`}/>
                <Legend />
                <Line type="monotone" dataKey="Portfolio" stroke="#2dd4bf" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="SPY" stroke="#64748b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* YEARLY TABLE */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
             <div className="p-4 border-b border-slate-700 font-bold text-white">Yearly Performance</div>
             <table className="w-full text-sm text-left text-slate-300">
               <thead className="text-xs text-slate-400 uppercase bg-slate-900/50">
                 <tr>
                   <th className="px-6 py-3">Year</th>
                   <th className="px-6 py-3">Strategy</th>
                   <th className="px-6 py-3">SPY</th>
                   <th className="px-6 py-3">Excess</th>
                   {/* NEW COLUMN HEADER */}
                   <th className="px-6 py-3">Top Holdings (Avg)</th>
                 </tr>
               </thead>
               <tbody>
                 {result.yearly_table.map((row) => (
                   <tr key={row.year} className="border-b border-slate-700 hover:bg-slate-700/50">
                     <td className="px-6 py-4 font-mono">{row.year}</td>
                     <td className={`px-6 py-4 font-bold ${row.portfolio > 0 ? "text-green-400" : "text-red-400"}`}>{(row.portfolio * 100).toFixed(1)}%</td>
                     <td className="px-6 py-4">{(row.spy * 100).toFixed(1)}%</td>
                     <td className={`px-6 py-4 font-bold ${row.diff > 0 ? "text-blue-400" : "text-slate-500"}`}>{(row.diff > 0 ? "+" : "")}{(row.diff * 100).toFixed(1)}%</td>
                     {/* NEW DATA CELL */}
                     <td className="px-6 py-4 text-xs font-mono text-slate-400">
                        {row.top_holdings}
                     </td>
                   </tr>
                 ))}
               </tbody>
             </table>
          </div>
        </div>
      )}
    </div>
  )
}

