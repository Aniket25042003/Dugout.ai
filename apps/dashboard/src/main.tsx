/**
 * @file apps/dashboard/src/main.tsx
 * @layer Frontend — Dashboard Bootstrap
 * @description Mounts the React dashboard application into the Vite root element.
 * @dependencies React StrictMode, createRoot, App component, index.css
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
