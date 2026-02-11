import { BookOpen, Clock, Shield, Activity, Target, ArrowRight, AlertTriangle } from 'lucide-react';

export default function HowToUse() {
  return (
    <div className="max-w-7xl mx-auto space-y-12 animate-fade-in pb-12">
      {/* HEADER */}
      <header className="space-y-4 text-center lg:text-left">
        <h1 className="text-4xl font-extrabold text-white">
          How to <span className="text-blue-500">Master the Strategy</span>
        </h1>
        <p className="text-lg text-slate-400 max-w-2xl">
          This model is a <strong>Macro-Quantitative Engine</strong>. It updates daily to track risks, 
          but successful investing requires discipline. Here is your protocol for stability.
        </p>
      </header>

      {/* THE CORE PHILOSOPHY */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 relative overflow-hidden group hover:border-blue-500/50 transition duration-300">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition">
                <Activity size={120} />
            </div>
            <div className="relative z-10 space-y-4">
                <div className="bg-blue-500/20 w-12 h-12 rounded-lg flex items-center justify-center text-blue-400">
                    <Activity size={24} />
                </div>
                <h3 className="text-xl font-bold text-white">High Sensitivity</h3>
                <p className="text-slate-400 text-sm leading-relaxed">
                    Our Dashboard acts like a sophisticated seismograph. It reacts to <strong>every</strong> market tremor 
                    (volatility, momentum shifts) in real-time. If the market sneezes, the Optimal Allocation might shift by 5-10%.
                </p>
            </div>
        </div>

        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 relative overflow-hidden group hover:border-purple-500/50 transition duration-300">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition">
                <Shield size={120} />
            </div>
             <div className="relative z-10 space-y-4">
                <div className="bg-purple-500/20 w-12 h-12 rounded-lg flex items-center justify-center text-purple-400">
                    <Shield size={24} />
                </div>
                <h3 className="text-xl font-bold text-white">Institutional Discipline</h3>
                <p className="text-slate-400 text-sm leading-relaxed">
                    Real institutions <strong>do not</strong> trade every day. Trading daily destroys returns through transaction fees (churn) 
                    and tax events. The goal is to capture the <em>Trend</em>, not the <em>Noise</em>.
                </p>
            </div>
        </div>

        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 relative overflow-hidden group hover:border-green-500/50 transition duration-300">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition">
                <Target size={120} />
            </div>
             <div className="relative z-10 space-y-4">
                <div className="bg-green-500/20 w-12 h-12 rounded-lg flex items-center justify-center text-green-400">
                    <Target size={24} />
                </div>
                <h3 className="text-xl font-bold text-white">The "Buffett" Buffer</h3>
                <p className="text-slate-400 text-sm leading-relaxed">
                    Our Backtest Engine proves that the best performance comes from waiting. 
                    It intentionally <strong>ignores</strong> small changes (under 8%) and only acts when the signal is strong.
                </p>
            </div>
        </div>
      </div>

      {/* THE 3-STEP PROTOCOL */}
      <div className="space-y-8">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <BookOpen className="text-blue-500" /> The Investor Protocol
        </h2>
        
        <div className="relative border-l-2 border-slate-700 ml-4 md:ml-6 space-y-12">
            
            {/* STEP 1 */}
            <div className="relative pl-8 md:pl-12">
                <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-blue-500 ring-4 ring-slate-900" />
                <h3 className="text-xl font-bold text-white mb-2">Step 1: The "Day 1" Allocation</h3>
                <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700">
                    <p className="text-slate-300 mb-4">
                        Look at the <strong>Dashboard Optimal Allocation</strong> pie chart. This is your starting point.
                        Buy these ETFs in the exact percentages shown today.
                    </p>
                    <div className="flex items-center gap-4 text-sm text-blue-400 bg-blue-500/10 p-3 rounded-lg w-fit">
                        <Target size={16} /> 
                        <span>Goal: Align your portfolio with the current Regime (Low/High Vol).</span>
                    </div>
                </div>
            </div>

            {/* STEP 2 */}
            <div className="relative pl-8 md:pl-12">
                <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-slate-600 ring-4 ring-slate-900" />
                <h3 className="text-xl font-bold text-white mb-2">Step 2: The "Freeze" Period</h3>
                <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700">
                    <p className="text-slate-300 mb-4">
                        <strong>Do not check the website tomorrow.</strong> Serious investing is boring. 
                        Set a calendar reminder for <strong>3 Months</strong> from today.
                    </p>
                    <div className="flex items-center gap-4 text-sm text-orange-400 bg-orange-500/10 p-3 rounded-lg w-fit">
                        <AlertTriangle size={16} /> 
                        <span>Warning: Checking daily leads to emotional trading. Trust the math and wait.</span>
                    </div>
                </div>
            </div>

            {/* STEP 3 */}
            <div className="relative pl-8 md:pl-12">
                <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-green-500 ring-4 ring-slate-900" />
                <h3 className="text-xl font-bold text-white mb-2">Step 3: The "Smart" Rebalance</h3>
                <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700">
                    <p className="text-slate-300 mb-4">
                        On day 90, open the Dashboard again. Compare your <strong>current holdings</strong> vs. the <strong>new Optimal Allocation</strong>.
                    </p>
                    <ul className="space-y-3 text-sm text-slate-400 mb-4">
                        <li className="flex items-start gap-2">
                            <span className="text-red-400 font-mono">IF</span> 
                            difference is small (e.g., Tech moved 25% → 27%) 
                            <ArrowRight size={16} className="text-slate-600"/> 
                            <span className="text-white font-bold">DO NOTHING.</span> This is noise.
                        </li>
                        <li className="flex items-start gap-2">
                             <span className="text-green-400 font-mono">IF</span> 
                            difference is large (e.g., Tech moved 25% → 10%) 
                            <ArrowRight size={16} className="text-slate-600"/> 
                            <span className="text-white font-bold">TRADE.</span> The regime has changed.
                        </li>
                    </ul>
                </div>
            </div>

        </div>
      </div>

      {/* FOOTER NOTE */}
      <div className="bg-blue-600/10 border border-blue-500/30 p-6 rounded-xl flex items-start gap-4">
        <Clock className="text-blue-400 shrink-0 mt-1" />
        <div>
            <h4 className="font-bold text-white text-lg">Why 3 Months?</h4>
            <p className="text-slate-400 text-sm mt-1">
                Our Backtest Engine uses a <strong>63-Trading-Day (1 Quarter)</strong> rebalancing frequency. 
                The excess returns shown in the backtest were achieved by waiting, not by chasing daily candles.
            </p>
        </div>
      </div>

    </div>
  );
}
