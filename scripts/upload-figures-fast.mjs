// Fast, resumable uploader for figure images to the Netlify Blob store `figures`.
//
// Strategy (much faster than get-then-set):
//   1. Snapshot all keys already in the store ONCE (paginated list()).
//   2. Upload only the files whose key is missing, at high concurrency.
//
// Re-running after an interruption is safe: the snapshot skips what's there.
//
// Creds: NETLIFY_SITE_ID + NETLIFY_AUTH_TOKEN env, else falls back to the
// linked project (.netlify/state.json) + local CLI config.
//
// Usage: node scripts/upload-figures-fast.mjs
import fs from 'fs';
import path from 'path';
import { getStore } from '@netlify/blobs';

const FIGURES_DIR = path.join(process.cwd(), 'backend', 'public', 'figures');
const CONCURRENCY = 40;

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
    console.error('Set NETLIFY_SITE_ID + NETLIFY_AUTH_TOKEN, or run `netlify login` first.');
    process.exit(1);
  }
  return { siteID, token };
}

async function main() {
  const { siteID, token } = resolveCreds();
  const store = getStore({ name: 'figures', siteID, token });
  const files = walk(FIGURES_DIR);
  console.log(`[fast-upload] ${files.length} local files`);

  // 1) snapshot existing keys
  const existing = new Set();
  let cursor;
  let pages = 0;
  do {
    const res = await store.list({ cursor });
    for (const b of res.blobs || []) existing.add(b.key);
    cursor = res.cursor;
    pages++;
  } while (cursor);
  console.log(`[fast-upload] store already has ${existing.size} blobs (${pages} pages)`);

  // 2) queue only missing
  const queue = [];
  for (const f of files) {
    const key = path.relative(FIGURES_DIR, f).split(path.sep).join('/');
    if (!existing.has(key)) queue.push({ f, key, retries: 0 });
  }
  console.log(`[fast-upload] ${queue.length} files to upload`);

  let uploaded = 0;
  let failed = 0;

  async function worker() {
    while (queue.length) {
      const job = queue.shift();
      try {
        const buf = fs.readFileSync(job.f);
        await store.set(job.key, buf);
        uploaded++;
      } catch (e) {
        if (job.retries < 3) {
          queue.push({ ...job, retries: job.retries + 1 });
        } else {
          failed++;
          console.error(`  FAIL ${job.key}: ${e.message}`);
        }
      }
      const done = uploaded + failed;
      if (done % 1000 === 0) console.log(`[fast-upload] ${done}/${queue.length + done} (uploaded ${uploaded}, failed ${failed})`);
    }
  }

  await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()));
  console.log(`[fast-upload] DONE uploaded=${uploaded}, failed=${failed} (of ${files.length})`);
  if (failed) process.exit(1);
}

main().catch((e) => {
  console.error('[fast-upload] failed:', e);
  process.exit(1);
});
