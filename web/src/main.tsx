import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import '../static/css/style.css';
import '../static/css/site.css';

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

import '../static/css/admin.css';
