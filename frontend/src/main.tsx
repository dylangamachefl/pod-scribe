import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import { AudioProvider } from './context/AudioContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <BrowserRouter>
            <AudioProvider>
                <App />
            </AudioProvider>
        </BrowserRouter>
    </React.StrictMode>,
)
