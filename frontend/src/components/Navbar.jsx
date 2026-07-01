import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, History, BookOpen, HelpCircle, Layers, ChevronLeft,
} from 'lucide-react';

// Per-strategy sub-navigation. Register future models here the same way.
const MODEL_NAV = {
  defensive: {
    label: 'Defensive',
    base: '/defensive',
    tabs: [
      { to: '/defensive', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/defensive/backtest', label: 'Backtest Engine', icon: History },
      { to: '/defensive/info', label: 'Model Logic', icon: BookOpen },
      { to: '/defensive/how-to-use', label: 'User Guide', icon: HelpCircle },
    ],
  },
};

export default function Navbar() {
  const location = useLocation();
  const path = location.pathname;

  // Detect which model (if any) we are currently inside.
  const modelKey = Object.keys(MODEL_NAV).find(
    (k) => path === MODEL_NAV[k].base || path.startsWith(MODEL_NAV[k].base + '/'),
  );
  const model = modelKey ? MODEL_NAV[modelKey] : null;

  const tabClass = (tab) => {
    const active = tab.end
      ? path === tab.to
      : path === tab.to || path.startsWith(tab.to + '/');
    return active
      ? 'bg-slate-700 text-blue-400'
      : 'text-slate-400 hover:text-white hover:bg-slate-800';
  };

  return (
    <nav className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">

          {/* BRAND */}
          <Link to="/" className="flex items-center gap-2">
            <div className="bg-blue-600 p-1.5 rounded-lg">
              <Layers className="text-white" size={20} />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">
              Strategy <span className="text-blue-500">Lab</span>
            </span>
          </Link>

          {/* RIGHT: model sub-nav when inside a strategy, else a library label */}
          {model ? (
            <div className="flex items-center gap-1">
              <Link
                to="/"
                className="px-3 py-2 rounded-md text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition flex items-center gap-1"
              >
                <ChevronLeft size={16} /> <span className="hidden sm:inline">Strategies</span>
              </Link>
              <span className="hidden md:block h-5 w-px bg-slate-700 mx-1" />
              {model.tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <Link
                    key={tab.to}
                    to={tab.to}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition flex items-center gap-2 ${tabClass(tab)}`}
                  >
                    <Icon size={16} /> <span className="hidden md:inline">{tab.label}</span>
                  </Link>
                );
              })}
            </div>
          ) : (
            <span className="text-sm font-medium text-slate-500 uppercase tracking-wider">
              Strategy Library
            </span>
          )}

        </div>
      </div>
    </nav>
  );
}
