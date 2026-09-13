// ---------------------------------------------------------------------------
// backend/src/env.js
//
// Dependency-free .env loader. This module is imported FIRST by src/index.js so
// that modules which read process.env at import time (notably src/ai.js) already
// see the values.
//
// Rules:
//   - A variable already present in the real environment always wins (so shell,
//     CI and Netlify dashboard values are never overridden by a stray .env).
//   - Values are never logged.
//   - Missing/unreadable files are silently ignored.
// ---------------------------------------------------------------------------

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

// Look in backend/.env first, then the project root .env.
const candidates = [
  path.join(here, '..', '.env'),
  path.join(here, '..', '..', '.env')
];

for (const file of candidates) {
  try {
    if (!fs.existsSync(file)) continue;
    const text = fs.readFileSync(file, 'utf8');
    for (const rawLine of text.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith('#')) continue;
      const eq = line.indexOf('=');
      if (eq === -1) continue;
      const key = line.slice(0, eq).trim();
      if (!key) continue;
      let val = line.slice(eq + 1).trim();
      if (
        (val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))
      ) {
        val = val.slice(1, -1);
      }
      if (process.env[key] === undefined) process.env[key] = val;
    }
  } catch {
    // ignore — env can still come from the shell
  }
}
