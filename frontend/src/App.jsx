import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import LakeDetail from './pages/LakeDetail';
import LandingPage from './pages/LandingPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/lake/:id" element={<LakeDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
