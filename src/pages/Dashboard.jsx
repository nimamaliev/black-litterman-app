import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  AreaChart, Area, Line, XAxis, YAxis, CartesianGrid
} from 'recharts'
import {
  Shield, Activity, Calendar, Plus, ArrowRightLeft,
  HelpCircle, Info, TrendingUp, AlertTriangle
} from 'lucide-react'

// --- CONSTANTS ---
const COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899',
  '#06b6d4', '#f97316', '#6366f1', '#84cc16', '#14b8a6'
];

const SECTOR_MAP = {
  'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy', 'XLV': 'Healthcare',
  'XLI': 'Industrials', 'XLC': 'Communication', 'XLP': 'Staples', 'XLU': 'Utilities',
  'XLY': 'Discretionary', 'XLB': 'Materials', 'XLRE': 'Real Estate'
};

const TEMPLATES = {
  ai_boom: { name: "AI Tech Supercycle", views: [{ ticker: 'XLK', value: 0.15, confidence: 0.80 }, { ticker: 'XLC', value: 0.10, confidence: 0.60 }] },
  inflation: { name: "Inflation Hedge", views: [{ ticker: 'XLE', value: 0.12, confidence: 0.70 }, { ticker: 'XLB', value: 0.08, confidence: 0.60 }] },
  recession: { name: "Defensive / Recession", views: [{ ticker: 'XLP', value: 0.08, confidence: 0.75 }, { ticker: 'XLV', value: 0.08, confidence: 0.70 }] }
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [targetDate, setTargetDate] = useState("");
  const [scenarioViews, setScenarioViews] = useState([]);
  const [mcData, setMcData] = useState(null);
  const [activeTab, setActiveTab] = useState("simple");
  const [newView, setNewView] = useState({ ticker: 'XLK', value: 0.05, confidence: 0.50 });
  const [pairView, setPairView] = useState({ assetA: 'XLK', assetB: 'XLE', diff: 0.05, confidence: 0.50 });

  const today = new Date().toISOString().split("T")[0];

  useEffect(() => { runScenario(); }, []);

  const runScenario = () => {
    const payload = { views: scenarioViews, date: targetDate || null };
    setLoading(true);
    axios.post('http://127.0.0.1:8000/recommendation/scenario', payload)
      .then(res => { setData(res.data); setLoading(false); setMcData(null); })
      .catch(err => { console.error(err); setLoading(false); });
  };

  const runMonteCarlo = () => {
    if (!data) return;
    axios.post('http://127.0.0.1:8000/simulation/monte_carlo', {
      mu: data.metrics.expected_return,
      sigma: data.metrics.volatility,
      days: 252
    }).then(res => {
      // Merge sample paths into the main data array for Recharts
      const points = res.data.days.map((day, i) => {
        let point = {
          day,
          p05: res.data.p05[i],
          p25: res.data.p25[i],
          p50: res.data.p50[i],
          p75: res.data.p75[i],
          p95: res.data.p95[i],
        };
        // Add individual sample lines
        if (res.data.sample_paths) {
            res.data.sample_paths.forEach((path, idx) => {
                point[`sim${idx}`] = path[i];
            });
        }
        return point;
      });

      setMcData({
        points: points,
        final_median: res.data.p50[res.data.p50.length - 1],
        final_low: res.data.p05[res.data.p05.length - 1],
        final_high: res.data.p95[res.data.p95.length - 1],
        count: res.data.simulation_count || 5000
      });
    });
  };

  // Handlers
  const addSimpleView = () => setScenarioViews([...scenarioViews, { ...newView }]);
  const addPairView = () => {
    const half = pairView.diff / 2;
    setScenarioViews([...scenarioViews, { ticker: pairView.assetA, value: half, confidence: pairView.confidence }, { ticker: pairView.assetB, value: -half, confidence: pairView.confidence }]);
  };
  const applyTemplate = (key) => key && setScenarioViews([...TEMPLATES[key].views]);
  const removeView = (i) => { const u = [...scenarioViews]; u.splice(i, 1); setScenarioViews(u); };

  if (loading || !data) return <div className="flex items-center justify-center h-screen text-blue-400 font-mono animate-pulse">Initializing Neural Engine...</div>;

  const sortedSectors = Object.entries(data.weights).sort((a, b) => b[1] - a[1]);
  const chartData = sortedSectors.filter(([_, v]) => v > 0.001).map(([n, v]) => ({ name: n, fullName: SECTOR_MAP[n], value: v }));

  const legendData = Object.keys(SECTOR_MAP).map(ticker => ({
    ticker,
    name: SECTOR_MAP[ticker],
    weight: data.weights[ticker] || 0
  })).sort((a, b) => b.weight - a.weight);

  const sharpe = (data.metrics.expected_return / (data.metrics.volatility + 0.0001)).toFixed(2);

  return (
    <div className="space-y-8 animate-fade-in pb-12">

        {/* HEADER */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl md:text-4xl font-extrabold text-white">Model <span className="text-blue-500">Dashboard</span></h1>
            <p className="text-slate-500 mt-1 font-mono text-sm uppercase tracking-wider">Regime: {data.regime.volatility}</p>
          </div>
          <div className="flex items-center gap-3 bg-slate-800 p-2 pl-4 rounded-lg border border-slate-700 mt-4 md:mt-0 shadow-lg">
             <div className="flex flex-col">
               <label className="text-[10px] text-slate-400 font-bold uppercase">Time Machine</label>
               <input type="date" className="bg-transparent text-white font-mono text-sm outline-none cursor-pointer"
                 value={targetDate} onChange={(e) => setTargetDate(e.target.value)} max={today} />
             </div>
             <button onClick={runScenario} className="bg-blue-600 p-2 rounded-md hover:bg-blue-500 transition"><Calendar size={18} /></button>
          </div>
        </header>

        {/* TOP ROW */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* KPI */}
          <div className="space-y-4">
             <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex justify-between items-center">
                <div>
                  <p className="text-slate-400 text-[10px] uppercase font-bold">Model Date</p>
                  <p className="text-xl font-mono font-bold text-white">{data.date}</p>
                </div>
                <Calendar className="text-slate-500" size={24} />
             </div>
             <div className="grid grid-cols-2 gap-4">
               <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                  <p className="text-slate-400 text-[10px] uppercase font-bold">Exp. Return</p>
                  <p className="text-2xl font-mono font-bold text-green-400">{(data.metrics.expected_return * 100).toFixed(1)}%</p>
               </div>
               <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                  <p className="text-slate-400 text-[10px] uppercase font-bold">Volatility</p>
                  <p className="text-2xl font-mono font-bold text-orange-400">{(data.metrics.volatility * 100).toFixed(1)}%</p>
               </div>
               <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                  <p className="text-slate-400 text-[10px] uppercase font-bold">Exp. Sharpe</p>
                  <p className="text-2xl font-mono font-bold text-blue-400">{sharpe}</p>
               </div>
               <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                  <p className="text-slate-400 text-[10px] uppercase font-bold">Risk Level</p>
                  <p className="text-xl font-bold text-white uppercase">{data.metrics.volatility > 0.18 ? "High" : "Moderate"}</p>
               </div>
             </div>
             {/* SECTOR LIST */}
             <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 max-h-[220px] overflow-y-auto">
               <h4 className="text-xs font-bold text-slate-400 uppercase mb-3">Full Sector Breakdown</h4>
               <div className="space-y-2">
                 {legendData.map((item, idx) => (
                   <div key={item.ticker} className="flex justify-between items-center text-sm hover:bg-slate-700/30 p-1 rounded">
                     <div className="flex items-center gap-2">
                       <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.weight > 0 ? COLORS[idx % COLORS.length] : '#334155' }}></div>
                       <span className={item.weight > 0 ? "text-white font-medium" : "text-slate-500"}>{item.ticker}</span>
                       <span className="text-xs text-slate-500 hidden xl:block truncate max-w-[80px]">- {item.name}</span>
                     </div>
                     <span className={`font-mono ${item.weight > 0 ? "text-white" : "text-slate-600"}`}>{(item.weight * 100).toFixed(1)}%</span>
                   </div>
                 ))}
               </div>
             </div>
          </div>

          {/* PIE CHART */}
          <div className="lg:col-span-2 bg-slate-800 p-6 rounded-xl border border-slate-700 min-h-[400px]">
            <h2 className="text-sm font-bold text-slate-300 uppercase tracking-wide mb-4">Optimal Allocation</h2>
            <ResponsiveContainer width="100%" height={350}>
              <PieChart>
                <Pie
                  data={chartData} cx="50%" cy="50%" innerRadius={80} outerRadius={120} paddingAngle={4} dataKey="value" stroke="none"
                  label={({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }) => {
                    const RADIAN = Math.PI / 180;
                    const radius = outerRadius * 1.25;
                    const x = cx + radius * Math.cos(-midAngle * RADIAN);
                    const y = cy + radius * Math.sin(-midAngle * RADIAN);
                    return (
                      <text x={x} y={y} fill="white" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={11} fontWeight="bold">
                        {chartData[index].name} {(percent * 100).toFixed(0)}%
                      </text>
                    );
                  }}
                >
                  {chartData.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#fff'}} formatter={(val, name, props) => [`${(val*100).toFixed(1)}%`, props.payload.fullName]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* BOTTOM ROW */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* STRATEGY BUILDER */}
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 flex flex-col">
               <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-white flex items-center gap-2"><Activity size={20} className="text-purple-400"/> Strategy Overlay</h3>
                  <div className="flex bg-slate-900 rounded p-1">
                    {['simple', 'pair', 'template'].map(t => (
                      <button key={t} onClick={() => setActiveTab(t)} className={`px-3 py-1 text-xs uppercase font-bold rounded ${activeTab === t ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'}`}>{t}</button>
                    ))}
                  </div>
               </div>

               {/* VIEW INPUTS */}
               {activeTab === 'simple' && (
                 <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700/50 mb-4">
                    <div className="grid grid-cols-12 gap-3 items-end">
                       <div className="col-span-3">
                         <label className="text-[10px] text-slate-400 uppercase font-bold mb-1 block">Ticker</label>
                         <select className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-sm text-white" value={newView.ticker} onChange={e => setNewView({...newView, ticker: e.target.value})}>
                           {Object.keys(SECTOR_MAP).map(t => <option key={t}>{t}</option>)}
                         </select>
                       </div>
                       <div className="col-span-4">
                         <label className="text-[10px] text-slate-400 uppercase font-bold mb-1 flex items-center gap-1">
                           Excess Return <span title="Outperformance (0.05 = 5%)" className="cursor-help"><HelpCircle size={10} /></span>
                         </label>
                         <input type="number" step="0.01" className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-sm text-white" value={newView.value} onChange={e => setNewView({...newView, value: parseFloat(e.target.value)})}/>
                       </div>
                       <div className="col-span-3">
                         <label className="text-[10px] text-slate-400 uppercase font-bold mb-1 flex items-center gap-1">
                           Confidence <span title="Certainty (0.1-1.0)" className="cursor-help"><HelpCircle size={10} /></span>
                         </label>
                         <input type="number" step="0.1" className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-sm text-white" value={newView.confidence} onChange={e => setNewView({...newView, confidence: parseFloat(e.target.value)})}/>
                       </div>
                       <div className="col-span-2">
                         <button onClick={addSimpleView} className="w-full bg-blue-600 text-white p-2 rounded h-[38px] flex items-center justify-center hover:bg-blue-500 transition"><Plus size={16}/></button>
                       </div>
                    </div>
                 </div>
               )}

               {activeTab === 'pair' && (
                 <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700/50 mb-4">
                    <p className="text-xs text-slate-400 mb-2 flex items-center gap-2"><ArrowRightLeft size={12}/> Asset A outperforms Asset B</p>
                    <div className="grid grid-cols-12 gap-2 items-end">
                       <div className="col-span-3"><select className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-sm text-white" value={pairView.assetA} onChange={e => setPairView({...pairView, assetA: e.target.value})}>{Object.keys(SECTOR_MAP).map(t => <option key={t}>{t}</option>)}</select></div>
                       <div className="col-span-3"><select className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-sm text-white" value={pairView.assetB} onChange={e => setPairView({...pairView, assetB: e.target.value})}>{Object.keys(SECTOR_MAP).map(t => <option key={t}>{t}</option>)}</select></div>
                       <div className="col-span-3"><input type="number" step="0.01" className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-sm text-white" value={pairView.diff} onChange={e => setPairView({...pairView, diff: parseFloat(e.target.value)})}/></div>
                       <div className="col-span-3"><button onClick={addPairView} className="w-full bg-purple-600 text-white p-2 rounded text-xs font-bold hover:bg-purple-500 transition h-[38px]">Add Pair</button></div>
                    </div>
                 </div>
               )}

               {activeTab === 'template' && (
                 <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700/50 mb-4 flex gap-2 flex-wrap">
                   {Object.entries(TEMPLATES).map(([key, t]) => (
                     <button key={key} onClick={() => applyTemplate(key)} className="bg-slate-800 border border-slate-600 px-3 py-2 rounded text-xs text-white hover:bg-slate-700 transition">{t.name}</button>
                   ))}
                 </div>
               )}

               <div className="flex-1 bg-slate-900 rounded-lg p-3 overflow-y-auto border border-slate-800 space-y-2 mb-4">
                 {scenarioViews.length === 0 ? <p className="text-slate-600 text-xs italic text-center mt-4">No active views defined.</p> :
                   scenarioViews.map((v, i) => (
                     <div key={i} className="flex justify-between items-center bg-slate-800 p-2 rounded text-xs border border-slate-700">
                       <div className="flex gap-2"><span className="text-blue-400 font-bold">{v.ticker}</span> <span className="text-slate-300">{(v.value*100).toFixed(0)}%</span> <span className="text-slate-500">({v.confidence})</span></div>
                       <button onClick={() => removeView(i)} className="text-slate-500 hover:text-red-400">×</button>
                     </div>
                   ))
                 }
               </div>

               <div className="flex gap-3 mt-auto">
                 <button onClick={runScenario} className="flex-1 bg-slate-700 hover:bg-slate-600 py-3 rounded font-bold text-sm text-white transition">Update Allocation</button>
                 <button onClick={runMonteCarlo} className="flex-1 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-500 hover:to-teal-500 py-3 rounded font-bold text-sm text-white transition shadow-lg shadow-green-900/20">Run Monte Carlo</button>
               </div>
            </div>

            {/* MONTE CARLO CHART */}
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 flex flex-col">
               <div className="flex justify-between items-center mb-4">
                 <h3 className="font-bold text-white text-sm uppercase tracking-wide">Future Projection (1 Year)</h3>
                 {mcData && <span className="text-[10px] text-slate-500 bg-slate-900 px-2 py-1 rounded border border-slate-700">{mcData.count.toLocaleString()} Sims</span>}
               </div>

               <div className="flex-1 min-h-[200px]">
                 {!mcData ? (
                   <div className="h-full flex flex-col items-center justify-center text-slate-600">
                     <Activity size={32} className="mb-2 opacity-20" />
                     <p className="text-xs">Click "Run Monte Carlo" to see the future.</p>
                   </div>
                 ) : (
                   <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={mcData.points}>
                        <defs>
                          <linearGradient id="colorMid" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#2dd4bf" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#2dd4bf" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis hide />
                        <YAxis domain={['auto','auto']} width={35} tick={{fill:'#64748b', fontSize:10}} tickFormatter={(v)=>`$${v.toFixed(0)}`} />
                        <Tooltip contentStyle={{backgroundColor:'#0f172a', borderColor:'#334155'}} formatter={(v)=>`$${v.toFixed(0)}`} labelFormatter={() => ''} />

                        {/* Outer Cone (5th - 95th) */}
                        <Area type="monotone" dataKey="p95" stroke="none" fill="#1e293b" fillOpacity={0.5} />
                        <Area type="monotone" dataKey="p05" stroke="none" fill="#0f172a" fillOpacity={1.0} /> {/* Cutout for cone effect */}

                        {/* Inner Cone (25th - 75th) */}
                        <Area type="monotone" dataKey="p75" stroke="none" fill="#3b82f6" fillOpacity={0.15} />
                        <Area type="monotone" dataKey="p25" stroke="none" fill="#0f172a" fillOpacity={1.0} /> {/* Cutout */}

                        {/* Median Line */}
                        <Area type="monotone" dataKey="p50" stroke="#2dd4bf" strokeWidth={2} fill="none" />

                        {/* Sample Paths (Spaghetti Lines) */}
                        <Line type="monotone" dataKey="sim0" stroke="#64748b" strokeWidth={1} dot={false} strokeOpacity={0.4} />
                        <Line type="monotone" dataKey="sim1" stroke="#64748b" strokeWidth={1} dot={false} strokeOpacity={0.4} />
                        <Line type="monotone" dataKey="sim2" stroke="#64748b" strokeWidth={1} dot={false} strokeOpacity={0.4} />
                      </AreaChart>
                   </ResponsiveContainer>
                 )}
               </div>

               {mcData && (
                 <div className="mt-4 bg-slate-900/50 p-4 rounded-lg border border-slate-700/50 text-xs text-slate-400 space-y-2">
                   <div className="flex items-start gap-2 border-b border-slate-700 pb-2 mb-2">
                     <Info size={14} className="text-blue-400 shrink-0 mt-0.5" />
                     <p>
                       <strong>How to read this:</strong> We ran 5,000 simulations.
                       The dark cone is the 90% probability range. The inner blue cone is the likely (50%) range.
                       Thin lines are random possible futures.
                     </p>
                   </div>
                   <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="bg-slate-800 p-2 rounded">
                        <span className="block text-slate-500 text-[10px]">Unlucky</span>
                        <span className="text-red-400 font-bold">${mcData.final_low.toFixed(0)}</span>
                      </div>
                      <div className="bg-slate-800 p-2 rounded border border-blue-500/30">
                        <span className="block text-slate-500 text-[10px]">Expected</span>
                        <span className="text-green-400 font-bold">${mcData.final_median.toFixed(0)}</span>
                      </div>
                      <div className="bg-slate-800 p-2 rounded">
                        <span className="block text-slate-500 text-[10px]">Lucky</span>
                        <span className="text-blue-400 font-bold">${mcData.final_high.toFixed(0)}</span>
                      </div>
                   </div>
                 </div>
               )}
            </div>
        </div>
    </div>
  )
}