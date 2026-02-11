import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
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
            <Route path="/" element={<Dashboard />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/info" element={<Info />} />
            <Route path="/how-to-use" element={<HowToUse />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
