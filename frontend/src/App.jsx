import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import LandingPage from './pages/LandingPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route
          path="/lake/:id"
          element={
            <div className="route-placeholder">Lake detail coming soon</div>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
