import { BookOpen, Clock, Shield, Activity, Target, ArrowRight, AlertTriangle, Gauge } from 'lucide-react';

export default function HowToUse() {
  return (
    <div className="max-w-7xl mx-auto space-y-12 animate-fade-in pb-12">
      {/* HEADER */}
      <header className="space-y-4 text-center lg:text-left">
        <h1 className="text-4xl font-extrabold text-white">
          How to Use the <span className="text-blue-500">Defensive Model</span>
        </h1>
        <p className="text-lg text-slate-400 max-w-2xl">
          This is a <strong>capital-protection</strong> strategy. It updates daily to track risk and decide
          how much of your money should be in the market versus safely in cash &mdash; but acting on it well takes discipline.
        </p>
      </header>

      {/* CORE IDEAS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 relative overflow-hidden group hover:border-blue-500/50 transition duration-300">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition">
                <Activity size={120} />
            </div>
            <div className="relative z-10 space-y-4">
                <div className="bg-blue-500/20 w-12 h-12 rounded-lg flex items-center justify-center text-blue-400">
                    <Activity size={24} />
                </div>
                <h3 className="text-xl font-bold text-white">It Reads Risk Daily</h3>
                <p className="text-slate-400 text-sm leading-relaxed">
                    The model watches market volatility like a seismograph. As risk rises it dials your equity
                    exposure <strong>down</strong> toward cash; as markets calm it dials back <strong>up</strong>.
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
                <h3 className="text-xl font-bold text-white">Discipline Over Noise</h3>
                <p className="text-slate-400 text-sm leading-relaxed">
                    The defense is meant to play out over quarters, not hours. Trading on every daily wiggle just
                    burns fees and taxes. The goal is to dodge the big drawdowns, not the small ones.
                </p>
            </div>
        </div>

        <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 relative overflow-hidden group hover:border-green-500/50 transition duration-300">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition">
                <Gauge size={120} />
            </div>
             <div className="relative z-10 space-y-4">
                <div className="bg-green-500/20 w-12 h-12 rounded-lg flex items-center justify-center text-green-400">
                    <Gauge size={24} />
                </div>
                <h3 className="text-xl font-bold text-white">Cash Is a Feature</h3>
                <p className="text-slate-400 text-sm leading-relaxed">
                    Do not be surprised if the model tells you to be only <strong>70% invested</strong>. Holding the
                    rest in cash during turbulent regimes is exactly how the strategy keeps your losses shallow.
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
                <h3 className="text-xl font-bold text-white mb-2">Step 1: The &quot;Day 1&quot; Allocation</h3>
                <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700">
                    <p className="text-slate-300 mb-4">
                        Open the <strong>Dashboard</strong> and buy the sector ETFs in the percentages shown. Note the
                        overall <strong>exposure</strong>: if the model is defensive, you may hold part of your money in cash rather than fully invested.
                    </p>
                    <div className="flex items-center gap-4 text-sm text-blue-400 bg-blue-500/10 p-3 rounded-lg w-fit">
                        <Target size={16} />
                        <span>Goal: match both the sector mix and the recommended invested-vs-cash split.</span>
                    </div>
                </div>
            </div>

            {/* STEP 2 */}
            <div className="relative pl-8 md:pl-12">
                <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-slate-600 ring-4 ring-slate-900" />
                <h3 className="text-xl font-bold text-white mb-2">Step 2: Hold Through the Noise</h3>
                <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700">
                    <p className="text-slate-300 mb-4">
                        <strong>Do not check the website tomorrow.</strong> Good defensive investing is boring.
                        Set a calendar reminder for <strong>3 months</strong> from today.
                    </p>
                    <div className="flex items-center gap-4 text-sm text-orange-400 bg-orange-500/10 p-3 rounded-lg w-fit">
                        <AlertTriangle size={16} />
                        <span>Warning: checking daily leads to emotional trading. Trust the math and wait.</span>
                    </div>
                </div>
            </div>

            {/* STEP 3 */}
            <div className="relative pl-8 md:pl-12">
                <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-green-500 ring-4 ring-slate-900" />
                <h3 className="text-xl font-bold text-white mb-2">Step 3: The Quarterly Rebalance</h3>
                <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700">
                    <p className="text-slate-300 mb-4">
                        On day 90, reopen the Dashboard and compare your <strong>current holdings</strong> against the <strong>new allocation and exposure</strong>.
                    </p>
                    <ul className="space-y-3 text-sm text-slate-400 mb-4">
                        <li className="flex items-start gap-2">
                            <span className="text-red-400 font-mono">IF</span>
                            the change is small (e.g. Tech 25% &rarr; 27%)
                            <ArrowRight size={16} className="text-slate-600"/>
                            <span className="text-white font-bold">DO NOTHING.</span> That is noise.
                        </li>
                        <li className="flex items-start gap-2">
                             <span className="text-green-400 font-mono">IF</span>
                            the change is large, or exposure dropped sharply (e.g. 100% &rarr; 65% invested)
                            <ArrowRight size={16} className="text-slate-600"/>
                            <span className="text-white font-bold">TRADE.</span> The regime has shifted.
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
                The strategy rebalances on a <strong>63-trading-day (1 quarter)</strong> cycle. Its risk protection
                was measured at that cadence &mdash; reacting more often adds cost and noise without adding safety.
            </p>
        </div>
      </div>

    </div>
  );
}
