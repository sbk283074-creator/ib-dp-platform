// Pure-JS Turso/libSQL client over the Hrana v2 HTTP pipeline API.
//
// Why this exists: @libsql/client pulls in a platform-specific native binary
// (@libsql/linux-x64-gnu). Netlify's CLI deploys bundle functions on the
// developer's local machine (macOS here), where that Linux-only binary cannot
// be installed — so the deployed function always crashed with
// "Cannot find module '@libsql/linux-x64-gnu'". This client uses the global
// `fetch` (available on Node 18+) and the Turso REST pipeline, so it has ZERO
// native dependencies and deploys cleanly to any serverless runtime.
//
// It implements the minimal surface that db.js actually uses:
//   client.execute({ sql, args })  -> { rows, columns, lastInsertRowid, rowsAffected }
//   client.executeMultiple(sql)    -> runs many `;`-separated statements
// `args` is a plain JS array (strings, numbers, null, boolean) — exactly what
// db.js's `sanitize()` already produces.

function argToHrana(v) {
  if (v === null || v === undefined) return { type: 'null', value: null };
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return { type: 'integer', value: String(v) };
    return { type: 'real', value: String(v) };
  }
  if (typeof v === 'boolean') return { type: 'integer', value: v ? '1' : '0' };
  return { type: 'text', value: String(v) };
}

function cellToJs(cell) {
  if (!cell || cell.type === 'null' || cell.value === null) return null;
  switch (cell.type) {
    case 'integer':
    case 'real':
      // API returns numeric values as strings; coerce to JS number to mirror
      // @libsql/client's return shape (downstream code does arithmetic on these).
      return Number(cell.value);
    case 'text':
      return cell.value;
    default:
      return cell.value;
  }
}

function mapResult(result) {
  const columns = (result.cols || []).map((c) => c.name);
  const rows = (result.rows || []).map((row) => row.map(cellToJs));
  return {
    columns,
    rows,
    lastInsertRowid: result.last_insert_rowid == null ? null : result.last_insert_rowid,
    rowsAffected: result.affected_row_count || 0
  };
}

function normalizeUrl(url) {
  return url.replace(/\/+$/, '') + '/v2/pipeline';
}

export function createClient({ url, authToken }) {
  const endpoint = normalizeUrl(url);
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${authToken}`
  };

  async function pipeline(statements) {
    const requests = statements.map((s) => ({
      type: 'execute',
      stmt: { sql: s.sql, args: (s.args || []).map(argToHrana) }
    }));
    requests.push({ type: 'close' });

    const res = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify({ requests })
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`Turso HTTP ${res.status}: ${text || res.statusText}`);
    }
    const data = await res.json();
    const results = data.results || [];
    // Surface the first error in the batch.
    for (const r of results) {
      if (r && r.type === 'error') {
        const msg = (r.error && r.error.message) || 'Turso pipeline error';
        throw new Error(msg);
      }
    }
    return results;
  }

  return {
    async execute(input) {
      // @libsql/client's execute() accepts either a SQL string or an object
      // { sql, args }. Normalize both forms here.
      const sql = typeof input === 'string' ? input : input.sql;
      const args = typeof input === 'string' ? [] : input.args || [];
      const results = await pipeline([{ sql, args }]);
      const ok = results.find((r) => r.type === 'ok' && r.response && r.response.type === 'execute');
      return mapResult((ok && ok.response.result) || { cols: [], rows: [] });
    },

    async executeMultiple(sql) {
      // Split on `;` that separates top-level statements. The schema DDL here
      // contains no `;`-inside-strings, so a naive split is safe.
      const statements = sql
        .split(';')
        .map((s) => s.trim())
        .filter((s) => s.length > 0)
        .map((s) => ({ sql: s, args: [] }));
      if (statements.length === 0) return;
      await pipeline(statements);
    }
  };
}

export default { createClient };
