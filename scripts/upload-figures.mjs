// Upload all figure images to the Netlify Blob store `figures`.
//
// The blob key for each file is its path relative to backend/public/figures
// (e.g. paper_aa_hl_p1/abc.jpg), which is exactly the path the frontend already
// requests as /figures/<key>. So no frontend change is needed.
//
// Resumable: files already present in the store are skipped, so you can re-run
// after an interruption without re-uploading everything.
//
// Requires Netlify auth: run `netlify login` (CLI) or set
//   NETLIFY_SITE_ID + NETLIFY_AUTH_TOKEN (CI).
//
// Usage:  npm run upload-figures
import fs from 'fs';
import path from 'path';
import { getStore } from '@netlify/blobs';

const FIGURES_DIR = path.join(process.cwd(), 'backend', 'public', 'figures');
const CONCURRENCY = 12;

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
  // Convenience: infer from a linked Netlify project + the local CLI config,
  // so `npm run upload-figures` works right after `netlify login` (no manual export).
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
  if (!fs.existsSync(FIGURES_DIR)) {
    console.error(`No figures directory at ${FIGURES_DIR}`);
    process.exit(1);
  }
  const { siteID, token } = resolveCreds();
  const store = getStore({ name: 'figures', siteID, token });
  const files = walk(FIGURES_DIR);
  console.log(`[upload] ${files.length} files to consider`);

  let uploaded = 0;
  let skipped = 0;
  let failed = 0;
  const queue = files.map((f) => ({ f, retries: 0 }));

  async function worker() {
    while (queue.length) {
      const { f, retries } = queue.shift();
      const key = path.relative(FIGURES_DIR, f).split(path.sep).join('/');
      try {
        const existing = await store.get(key);
        if (existing) {
          skipped++;
        } else {
          const buf = fs.readFileSync(f);
          await store.set(key, buf);
          uploaded++;
        }
      } catch (e) {
        if (retries < 3) {
          queue.push({ f, retries: retries + 1 });
        } else {
          failed++;
          console.error(`  FAIL ${key}: ${e.message}`);
        }
      }
      const total = uploaded + skipped + failed;
      if (total % 1000 === 0) console.log(`[upload] ${total}/${files.length} (uploaded ${uploaded}, skipped ${skipped}, failed ${failed})`);
    }
  }

  await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()));
  console.log(`[upload] done. uploaded=${uploaded}, skipped=${skipped}, failed=${failed} (of ${files.length})`);
  if (failed) process.exit(1);
}

main().catch((e) => {
  console.error('[upload] failed:', e);
  process.exit(1);
});
