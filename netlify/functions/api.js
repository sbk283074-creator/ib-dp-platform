// Netlify Function: serves the Express API as a serverless handler.
// Wraps the shared API app (backend/src/app.js) with serverless-http.
// The DB (Turso or local) is initialized once per cold start and reused.
import serverless from 'serverless-http';
import { createApp } from '../../backend/src/app.js';
import db from '../../backend/src/db.js';

const app = createApp();
const ready = db.init(); // module-scope promise, cached across warm starts
const slsHandler = serverless(app);

export const handler = async (event, context) => {
  await ready;
  return slsHandler(event, context);
};
