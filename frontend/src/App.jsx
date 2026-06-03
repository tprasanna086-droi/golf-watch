import './App.css'

function App() {
  return (
    <div className="app-container">
      <div className="hero">
        <div className="pulse-ring"></div>
        <h1 className="title">Glacial Risk Nepal — Live Monitor</h1>
        <p className="subtitle">System initializing…</p>
        <div className="status-bar">
          <span className="status-dot"></span>
          <span className="status-text">Connecting to satellite feeds</span>
        </div>
      </div>
    </div>
  )
}

export default App
