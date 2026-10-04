import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './shell/App';
import { applyTheme, migrateTheme } from './shell/themes';
import { store } from './store';
import './styles/fonts';
import './styles/themes.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/layouts.css';
import './styles/shell.css';
import './styles/print.css';
import './styles/art.css';

// Хранилище читает сохранённое состояние сразу при создании, поэтому тема ставится до первой отрисовки.
const theme = migrateTheme(store.getState().settings.view.theme);
if (theme !== store.getState().settings.view.theme) store.getState().patchView({ theme });
applyTheme(theme);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
// Заставка с танцором видна, пока программа грузится; показываем её хотя бы мгновение, чтобы не мигала.
window.setTimeout(() => (window as unknown as { __hideSplash?: () => void }).__hideSplash?.(), 900);
