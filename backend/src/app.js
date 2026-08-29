import express from 'express';
import cors from 'cors';
import api from './api.js';

/**
 * Build the Express API application (no listen / no static hosting).
 * Shared by the local dev server (index.js) and the Netlify Function
 * (netlify/functions/api.js).
 */
export function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: '12mb' }));
  app.use('/api', api);
  return app;
}

export default createApp;
