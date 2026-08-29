// Fast resumable figure uploader: snapshot existing blob keys ONCE via list(),
// then SET only the missing files at high concurrency (no per-file GET pre-check).
// Idempotent: safe to re-run; re-listing skips whatever is already stored.
import fs from 'fs';
import path from 'path';
import { getStore } from '@netlify/blobs';

const FIGURES_DIR = path.join(process.cwd(), 'backend', 'public', 'figures');
const CONCURRENCY = 40;

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

function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

async function main() {
  if (!fs.existsSync(FIGURES_DIR)) { console.error(`No figures dir at ${FIGURES_DIR}`); process.exit(1); }
  const { siteID, token } = resolveCreds();
  const store = getStore({ name: 'figures', siteID, token });

  // Snapshot existing keys once.
  const existing = new Set();
  let cursor = undefined;
  do {
    const page = await store.list({ limit: 1000, cursor });
    for (const b of page.blobs) existing.add(b.key);
    cursor = page.cursor || undefined;
  } while (cursor);
  console.log(`[fast] existing blobs snapshot: ${existing.size}`);

  const files = walk(FIGURES_DIR);
  const todo = files.filter((f) => {
    const key = path.relative(FIGURES_DIR, f).split(path.sep).join('/');
    return !existing.has(key);
  });
  console.log(`[fast] ${files.length} files total, ${todo.length} to upload`);

  let uploaded = 0;
  let failed = 0;
  const queue = todo.map((f) => ({ f, retries: 0 }));

  async function worker() {
    while (queue.length) {
      const { f, retries } = queue.shift();
      const key = path.relative(FIGURES_DIR, f).split(path.sep).join('/');
      try {
        const buf = fs.readFileSync(f);
        await store.set(key, buf);
        uploaded++;
      } catch (e) {
        if (retries < 5) queue.push({ f, retries: retries + 1 });
        else { failed++; console.error(`  FAIL ${key}: ${e.message}`); }
      }
      const total = uploaded + failed;
      if (total % 1000 === 0) console.log(`[fast] ${total}/${todo.length} (uploaded ${uploaded}, failed ${failed})`);
    }
  }

  await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()));
  console.log(`[fast] DONE uploaded=${uploaded}, failed=${failed} (of ${todo.length})`);
  if (failed) process.exit(1);
}

main().catch((e) => { console.error('[fast] failed:', e); process.exit(1); });
