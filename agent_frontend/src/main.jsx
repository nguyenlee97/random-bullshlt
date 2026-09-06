import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import AppRuntimeBoundary from './components/AppRuntimeBoundary.jsx'
import ScenarioLabPage from './components/ScenarioLabPage.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AppRuntimeBoundary>
      {window.location.pathname === '/evaluation/scenarios' ? <ScenarioLabPage /> : <App />}
    </AppRuntimeBoundary>
  </React.StrictMode>,
)
