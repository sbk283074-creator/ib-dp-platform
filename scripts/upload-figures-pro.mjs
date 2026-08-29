// Robust, resumable, high-concurrency uploader for figure images to the
// Netlify Blob store `figures`.
//
// Improvements over upload-figures-fast.mjs:
//   - concurrency configurable via argv[2] or CONC env (default 300)
//   - progress written with fs.appendFileSync (unbuffered) so it is visible
//     in the log file even though stdout is block-buffered when redirected
//   - re-running / restarting is safe: it re-snapshots existing keys first
//
// Usage: node scripts/upload-figures-pro.mjs [concurrency]
//        (or) CONC=300 node scripts/upload-figures-pro.mjs
import fs from 'fs';
import path from 'path';
import { getStore } from '@netlify/blobs';

const FIGURES_DIR = path.join(process.cwd(), 'backend', 'public', 'figures');
const CONCURRENCY = Number(process.argv[2] || process.env.CONC || 200);
const SET_TIMEOUT_MS = Number(process.env.SET_TIMEOUT_MS || 60000);
const LOG = process.env.UPLOAD_LOG || path.join('/tmp', 'upload_pro.log');

// Netlify Blobs client has no per-request timeout; without this, a stalled
// connection hangs the worker forever (never counts as done). Race each set
// against a timeout so it fails fast and is retried.
function setWithTimeout(store, key, buf) {
  return Promise.race([
    store.set(key, buf),
    new Promise((_, rej) => setTimeout(() => rej(new Error('set-timeout')), SET_TIMEOUT_MS)),
  ]);
}

function log(msg) {
  const line = `[pro-upload ${new Date().toISOString()}] ${msg}\n`;
  fs.appendFileSync(LOG, line); // synchronous + unbuffered -> always visible
}
function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}
function resolveCreds() {
  let siteID = process.env.NETLIFY_SITE_ID;
  let token = process.env.NETLIFY_AUTH_TOKEN;
  if (siteID && token) return { siteID, token };
  try {
    if (!siteID) {
      const st = JSON.parse(fs.readFileSync(path.join(process.cwd(), '.netlify', 'state.json'), 'utf8'));
      siteID = st.siteId;
    }
  } catch {}
  try {
    if (!token) {
      const cfg = JSON.parse(fs.readFileSync(process.env.HOME + '/Library/Preferences/netlify/config.json', 'utf8'));
      const u = Object.values(cfg.users || {})[0];
      token = u && u.auth && u.auth.token;
    }
  } catch {}
  if (!siteID || !token) {
    log('Set NETLIFY_SITE_ID + NETLIFY_AUTH_TOKEN, or run `netlify login` first.');
    process.exit(1);
  }
  return { siteID, token };
}

async function main() {
  const { siteID, token } = resolveCreds();
  const store = getStore({ name: 'figures', siteID, token });
  const files = walk(FIGURES_DIR);
  log(`${files.length} local files, concurrency=${CONCURRENCY}`);

  // 1) snapshot existing keys (Netlify returns them all in one response)
  const existing = new Set();
  let cursor;
  let pages = 0;
  do {
    const res = await store.list({ cursor });
    for (const b of res.blobs || []) existing.add(b.key);
    cursor = res.cursor;
    pages++;
  } while (cursor);
  log(`store already has ${existing.size} blobs (${pages} pages)`);

  // 2) queue only missing
  const queue = [];
  for (const f of files) {
    const key = path.relative(FIGURES_DIR, f).split(path.sep).join('/');
    if (!existing.has(key)) queue.push({ f, key, retries: 0 });
  }
  log(`${queue.length} files to upload`);

  let uploaded = 0;
  let failed = 0;
  let lastLog = 0;
  let lastLogTs = Date.now();

  async function worker() {
    while (queue.length) {
      const job = queue.shift();
      try {
        const buf = fs.readFileSync(job.f);
        await setWithTimeout(store, job.key, buf);
        uploaded++;
      } catch (e) {
        if (job.retries < 5) {
          queue.push({ ...job, retries: job.retries + 1 });
        } else {
          failed++;
          log(`  FAIL ${job.key}: ${e.message}`);
        }
      }
      const done = uploaded + failed;
      const now = Date.now();
      if (done - lastLog >= 250 || now - lastLogTs >= 20000) {
        lastLog = done;
        lastLogTs = now;
        log(`${done}/${queue.length + done} (uploaded ${uploaded}, failed ${failed})`);
      }
    }
  }

  await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()));
  log(`DONE uploaded=${uploaded}, failed=${failed} (of ${files.length})`);
  if (failed) process.exit(1);
}

main().catch((e) => {
  log('FATAL: ' + (e && e.stack ? e.stack : e));
  process.exit(1);
});
