import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Hub from './pages/Hub';
import Dashboard from './pages/Dashboard';
import Backtest from './pages/Backtest';
import Info from './pages/Info';
import HowToUse from './pages/HowToUse';

function App() {
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
