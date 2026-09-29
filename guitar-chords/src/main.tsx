import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';
import { migrateTheme } from './app/themes';
import './styles/fonts';
import './styles/themes.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/layouts.css';

// Тема ставится до первой отрисовки, чтобы при запуске не мелькало оформление по умолчанию.
try {
  document.documentElement.dataset.theme = migrateTheme(JSON.parse(localStorage.getItem('gc.view') ?? '{}')?.theme);
} catch {
  document.documentElement.dataset.theme = migrateTheme(undefined);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
