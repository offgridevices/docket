import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.tsx';
// Import order matters: Tailwind's layers first, then the brand tokens/fonts, so the
// brand's `html, body { background, color }` rule (tokens.css) wins any cascade tie
// against Tailwind's preflight reset — later import wins for equal specificity.
import './index.css';
import './brand/tokens.css';
import './brand/semantic.css';
import './brand/fonts.css';

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('#root element missing from index.html');

createRoot(rootEl).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
