import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { createApp } from './app.js';
import db from './db.js';
import { seedPaperTemplates } from './seed/paperTemplates.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 3001;

const app = createApp();

// Boot: open the DB (local SQLite or Turso), seed paper templates, then serve.
(async () => {
  await db.init();

  // F10: keep paper templates (per subject/paper) present
  try {
    const n = await seedPaperTemplates();
    console.log(`[ib-dp-backend] paper templates ready (${n})`);
  } catch (e) {
    console.warn('[ib-dp-backend] paper templates seed failed:', e.message);
  }

  // Local-only: serve figure images + the built frontend.
  const figuresDir = path.join(__dirname, '..', 'public', 'figures');
  if (fs.existsSync(figuresDir)) {
    app.use('/figures', express.static(figuresDir));
  }

  const frontendDist = path.join(__dirname, '..', '..', 'frontend', 'dist');
  if (fs.existsSync(frontendDist)) {
    app.use(express.static(frontendDist));
    app.get('*', (req, res) => res.sendFile(path.join(frontendDist, 'index.html')));
  }

  app.listen(PORT, () => {
    console.log(`[ib-dp-backend] listening on http://localhost:${PORT}`);
  });
})().catch((e) => {
  console.error('[ib-dp-backend] failed to start:', e);
  process.exit(1);
});
