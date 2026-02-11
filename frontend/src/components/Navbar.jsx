import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, History, BookOpen, Activity, HelpCircle } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();

  // Helper to apply active state styles
  const isActive = (path) => location.pathname === path 
    ? "bg-slate-700 text-blue-400" 
    : "text-slate-400 hover:text-white hover:bg-slate-800";

  return (
    <nav className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">

          {/* LOGO */}
          <Link to="/" className="flex items-center gap-2">
            <div className="bg-blue-600 p-1.5 rounded-lg">
              <Activity className="text-white" size={20} />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">
              Black-Litterman <span className="text-blue-500">AI</span>
            </span>
          </Link>

          {/* LINKS */}
          <div className="flex space-x-1">
            <Link to="/" className={`px-4 py-2 rounded-md text-sm font-medium transition flex items-center gap-2 ${isActive('/')}`}>
              <LayoutDashboard size={16} /> Dashboard
            </Link>
            
            <Link to="/backtest" className={`px-4 py-2 rounded-md text-sm font-medium transition flex items-center gap-2 ${isActive('/backtest')}`}>
              <History size={16} /> Backtest Engine
            </Link>
            
            <Link to="/info" className={`px-4 py-2 rounded-md text-sm font-medium transition flex items-center gap-2 ${isActive('/info')}`}>
              <BookOpen size={16} /> Model Logic
            </Link>

            {/* FIXED: Now uses the same styling logic and a unique icon */}
            <Link to="/how-to-use" className={`px-4 py-2 rounded-md text-sm font-medium transition flex items-center gap-2 ${isActive('/how-to-use')}`}>
              <HelpCircle size={16} /> User Guide
            </Link>
          </div>

        </div>
      </div>
    </nav>
  );
}
