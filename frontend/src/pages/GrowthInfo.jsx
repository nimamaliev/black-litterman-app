import { Gauge, TrendingUp, ShieldAlert, FlaskConical } from 'lucide-react';

function Card({ icon, title, children }) {
  const Icon = icon;
  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-3">
      <h3 className="font-bold text-white flex items-center gap-2"><Icon size={18} className="text-green-400" /> {title}</h3>
      <div className="text-sm text-slate-300 leading-relaxed space-y-2">{children}</div>
    </div>
  );
}

export default function GrowthInfo() {
  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-12">
      <header>
        <h1 className="text-3xl font-extrabold text-white">Growth <span className="text-green-500">Model Logic</span></h1>
        <p className="text-slate-400 mt-2">How the strategy works, what it assumes, and where it can fail.</p>
      </header>

      <Card icon={Gauge} title="The rule">
        <p>
          Once per day the model measures how volatile the S&amp;P 500 (SPY) has been over the last 21 trading days and sets its exposure to:
        </p>
        <p className="font-mono text-green-300 bg-slate-900/60 rounded-lg p-3 text-xs">
          exposure = clamp( target volatility &divide; recent SPY volatility , 0 , max leverage )
        </p>
        <p>
          Calm markets mean the ratio is large, so the model holds more than 100% of the portfolio in SPY, up to the leverage cap (default 1.5x).
          Turbulent markets mean the ratio is small, so it sells down toward cash. Any borrowed money costs the risk-free rate plus 1.5% a year;
          any cash earns the risk-free rate. Exposure is only re-sized when it moves by more than 0.10, and every change pays a 5 bps trading cost.
        </p>
      </Card>

      <Card icon={TrendingUp} title="Why it can beat SPY">
        <p>
          Volatility is far more predictable than returns: turbulent periods tend to cluster, and so do calm ones. Calm markets have also tended to be
          the ones that keep rising. Holding more when risk is low and less when it is high earns extra return in the good stretches and avoids a
          chunk of the worst crashes (see 2008 in the backtest). This is the &ldquo;volatility-managed portfolio&rdquo; effect described by Moreira and Muir (2017).
        </p>
        <p>
          Over 2006&ndash;2026 with default settings it returned about 13.3% a year against 11.1% for SPY, with a max drawdown near &minus;43% against &minus;55%.
          It beat SPY in both the 2007&ndash;2014 and the 2015&ndash;2026 halves of the data.
        </p>
      </Card>

      <Card icon={ShieldAlert} title="What to be careful about">
        <ul className="list-disc list-inside space-y-1.5">
          <li><span className="font-semibold text-white">It uses leverage.</span> The edge over SPY comes from holding up to 1.5x. Leverage magnifies losses, and borrowing costs vary. In 2022 the strategy fell slightly more than SPY.</li>
          <li><span className="font-semibold text-white">It reacts after volatility rises.</span> It cuts exposure only once markets are already swinging, so it can lag in sharp V-shaped rebounds (2020, 2009) and gives up some of the bounce.</li>
          <li><span className="font-semibold text-white">The edge is modest and uneven.</span> It beat SPY in roughly 12 of 21 calendar years. In the last decade the margin was about 1 percentage point a year, much smaller than in 2007&ndash;2014.</li>
          <li><span className="font-semibold text-white">It is a single-asset model.</span> It holds SPY and cash only, with no sector or stock selection.</li>
          <li><span className="font-semibold text-white">Real trading differs.</span> Margin rates, leveraged-ETF fees and taxes are not fully modelled, and daily rebalancing may not be practical.</li>
        </ul>
      </Card>

      <Card icon={FlaskConical} title="How it was tested">
        <ul className="list-disc list-inside space-y-1.5">
          <li>The exposure signal is lagged one day, so a day&rsquo;s return never influences that day&rsquo;s position.</li>
          <li>The default parameters sit in the middle of a smooth range: nearby volatility targets, lookbacks (10&ndash;63 days) and leverage caps all behave similarly, with more return coming with deeper drawdowns.</li>
          <li>Doubling the assumed borrowing spread to 3% still left it ahead of SPY.</li>
          <li>The data is a single historical path of one market (US large caps, 2005&ndash;2026), so treat the result as evidence, not proof.</li>
        </ul>
      </Card>

      <p className="text-center text-xs text-slate-600">
        Illustrative only, not investment advice. Past performance does not guarantee future results.
      </p>
    </div>
  );
}
