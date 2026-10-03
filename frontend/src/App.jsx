import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { API_BASE } from './config';
import Navbar from './components/Navbar';
import Hub from './pages/Hub';
import Dashboard from './pages/Dashboard';
import Backtest from './pages/Backtest';
import Info from './pages/Info';
import HowToUse from './pages/HowToUse';
import GrowthDashboard from './pages/GrowthDashboard';
import GrowthBacktest from './pages/GrowthBacktest';
import GrowthInfo from './pages/GrowthInfo';

function App() {
  // The free-tier backend sleeps when idle. Ping it as soon as the site opens so
  // it is already waking up while the user reads the page, not on their first click.
  useEffect(() => {
    fetch(`${API_BASE}/`, { method: 'GET', mode: 'cors' }).catch(() => {});
  }, []);

  return (
    <Router>
      <div className="min-h-screen bg-slate-900 text-slate-100 font-sans">
        <Navbar />
        <main className="p-4 md:p-8">
          <Routes>
            {/* Strategy Library (hub) */}
            <Route path="/" element={<Hub />} />

            {/* Defensive / Crash-Protection model */}
            <Route path="/defensive" element={<Dashboard />} />
            <Route path="/defensive/backtest" element={<Backtest />} />
            <Route path="/defensive/info" element={<Info />} />
            <Route path="/defensive/how-to-use" element={<HowToUse />} />

            {/* Growth model: volatility-managed SPY */}
            <Route path="/growth" element={<GrowthDashboard />} />
            <Route path="/growth/backtest" element={<GrowthBacktest />} />
            <Route path="/growth/info" element={<GrowthInfo />} />

            {/* Backwards-compatible redirects from the old single-model routes */}
            <Route path="/backtest" element={<Navigate to="/defensive/backtest" replace />} />
            <Route path="/info" element={<Navigate to="/defensive/info" replace />} />
            <Route path="/how-to-use" element={<Navigate to="/defensive/how-to-use" replace />} />

            {/* Anything else falls back to the hub */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
