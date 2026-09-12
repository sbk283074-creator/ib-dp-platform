// ---------------------------------------------------------------------------
// backend/src/ai.js
//
// Safe, dependency-free Groq FREE-TIER integration for the IB DP study assistant.
//
// ── COST SAFETY (hard guarantees) ──────────────────────────────────────────
//   - ONLY Groq's free endpoint (api.groq.com) is ever called. There is no paid
//     provider, no auto-upgrade, no billing endpoint and no paid model switch
//     anywhere in this file.
//   - No GROQ_API_KEY -> askAI() makes ZERO network calls and callers get
//     { configured:false }. Nothing here can incur a charge.
//   - Model rotation only ever moves WITHIN the free tier. A 429 makes us try
//     another FREE model; it never causes us to pay for one.
//
// ── PRIVACY SAFETY ─────────────────────────────────────────────────────────
//   - The key lives only in process.env (server-side). Never returned to the
//     client, never logged.
//   - Student prompts are never persisted. A short-lived in-memory response
//     cache (TTL) exists purely to save quota.
//   - Prompt TEXT is never logged — only metadata (subject, lengths, counters).
//   - Callers pass { message, questionId? }; the server grounds the prompt in
//     its own database, so the client never dictates raw prompt content.
//
// ── MAXIMISING THE FREE TIER ───────────────────────────────────────────────
//   Every Groq model has its OWN independent daily bucket, so a request that
//   hits a 429 on one model can be served immediately by the next. Pooling the
//   org's generation models multiplies usable capacity far beyond any single
//   model (numbers below mirror console.groq.com/settings/limits):
//
//       model                  RPM   RPD     TPM     TPD
//       openai/gpt-oss-120b     30   1,000   8,000   200,000   (prompt-cache)
//       openai/gpt-oss-20b      30   1,000   8,000   200,000   (prompt-cache)
//       qwen/qwen3.6-27b        30   1,000   8,000   200,000
//       qwen/qwen3.8-27b        30   1,000   8,000   200,000
//       groq/compound-mini      30     250  70,000   unlimited
//       groq/compound           30     250  70,000   unlimited
//       allam-2-7b              30   7,000   6,000   500,000   (bulk fallback)
//
//       aggregate ≈ 11,500 requests/day and >1.3M metered tokens/day,
//       versus 1,000 / 200k for any one model  →  ~11x the requests.
//
//   Two Groq behaviours are exploited deliberately:
//     1. CACHED PROMPT TOKENS DO NOT COUNT toward TPM/TPD (Groq docs). We
//        therefore send one large, byte-identical STATIC system prefix first
//        and keep the dynamic part small, so repeated calls hit Groq's automatic
//        prefix cache and their input tokens stop consuming the daily budget.
//     2. The x-ratelimit-* response headers are authoritative. We adopt the
//        server-reported remaining count per model, so our own ledger is only a
//        guard rail and the real limit is never the thing that surprises us.
// ---------------------------------------------------------------------------

import { createHash } from 'node:crypto';

const GROQ_BASE_URL = (process.env.GROQ_BASE_URL || 'https://api.groq.com/openai/v1').replace(/\/$/, '');
const API_KEY = process.env.GROQ_API_KEY || '';
const CONFIGURED = Boolean(API_KEY);

const MAX_TOKENS = Number(process.env.AI_MAX_TOKENS || 800);
const MAX_MESSAGE_CHARS = 1200;
const MAX_CONTEXT_CHARS = 2500;

// --- Free-tier registry (mirrors the org Limits page; reset 00:00 UTC) ------
const MODEL_LIMITS = {
  'openai/gpt-oss-120b': { rpm: 30, rpd: 1000, tpm: 8000, tpd: 200000, cache: true, label: 'GPT-OSS 120B' },
  'openai/gpt-oss-20b': { rpm: 30, rpd: 1000, tpm: 8000, tpd: 200000, cache: true, label: 'GPT-OSS 20B' },
  'qwen/qwen3.6-27b': { rpm: 30, rpd: 1000, tpm: 8000, tpd: 200000, cache: false, label: 'Qwen3 27B' },
  'qwen/qwen3.8-27b': { rpm: 30, rpd: 1000, tpm: 8000, tpd: 200000, cache: false, label: 'Qwen3.8 27B' },
  'groq/compound-mini': { rpm: 30, rpd: 250, tpm: 70000, tpd: Infinity, cache: false, label: 'Compound Mini' },
  'groq/compound': { rpm: 30, rpd: 250, tpm: 70000, tpd: Infinity, cache: false, label: 'Compound' },
  'allam-2-7b': { rpm: 30, rpd: 7000, tpm: 6000, tpd: 500000, cache: false, label: 'Allam 2 7B' }
};

// Best-quality first. Later members only get used when earlier ones are capped,
// so a normal day always runs on gpt-oss-120b. Order = quality, then failover.
const DEFAULT_POOL = [
  'openai/gpt-oss-120b',
  'openai/gpt-oss-20b',
  'qwen/qwen3.6-27b',
  'qwen/qwen3.8-27b',
  'groq/compound-mini',
  'groq/compound',
  'allam-2-7b'
];

const ENV_POOL = (process.env.GROQ_MODELS || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
const LEGACY_MODEL = (process.env.GROQ_MODEL || '').trim();

const POOL = (() => {
  let p = ENV_POOL.length ? ENV_POOL : DEFAULT_POOL.slice();
  if (LEGACY_MODEL && !p.includes(LEGACY_MODEL)) p = [LEGACY_MODEL, ...p];
  return [...new Set(p)];
})();

// Unknown models are allowed but never locally capped — we rely on Groq's own
// 429 + x-ratelimit headers for them, so we can't accidentally under-use them.
function limitsFor(model) {
  return MODEL_LIMITS[model] || { rpm: 30, rpd: Infinity, tpm: Infinity, tpd: Infinity, cache: false, label: model, unknown: true };
}

// ---------------------------------------------------------------------------
// Model capability reference (for the UI's "which model should I use?" guide).
// Sourced from Groq model docs + independent benchmarks (Artificial Analysis,
// OpenAI gpt-oss model card, Qwen releases). Strengths are deliberately short
// so they fit a compact panel; they are NON-authoritative descriptions, not a
// guarantee of output quality.
// ---------------------------------------------------------------------------
const MODEL_CAPS = {
  'openai/gpt-oss-120b': {
    vendor: 'OpenAI (open-weight)',
    size: '117B params (5.1B active / MoE)',
    strengths: ['Top reasoning & chain-of-thought', 'Strong math / physics / CS method', '131K context, 65K max output'],
    bestFor: 'Hardest problems, proofs, multi-step reasoning',
    note: "Groq's most capable reasoning model; near o4-mini on reasoning benchmarks."
  },
  'openai/gpt-oss-20b': {
    vendor: 'OpenAI (open-weight)',
    size: '21B params (3.6B active / MoE)',
    strengths: ['Very fast (~1000 tok/s)', 'Good reasoning for everyday questions', 'Cheapest per token'],
    bestFor: 'Quick checks and short explanations',
    note: 'Fastest model on Groq; ideal when you need a fast answer.'
  },
  'qwen/qwen3.6-27b': {
    vendor: 'Alibaba (open-weight)',
    size: '27B dense (hybrid attention)',
    strengths: ['Strong multilingual — best for Chinese (中文)', 'Reasoning + vision', '131K context'],
    bestFor: 'Chinese-language answers, general IB questions',
    note: 'Among the most capable general models on Groq.'
  },
  'qwen/qwen3.8-27b': {
    vendor: 'Alibaba (open-weight)',
    size: '27B dense (hybrid attention)',
    strengths: ['Strongest general reasoning on Groq', 'Excellent Chinese (中文)', 'Big coding/reasoning jump over 3.6', '131K context'],
    bestFor: 'Standard IB questions, especially in Chinese',
    note: 'Recommended default for most study questions.'
  },
  'groq/compound-mini': {
    vendor: 'Groq (system)',
    size: 'GPT-OSS 120B + Llama 3.3 70B + tools',
    strengths: ['Unlimited daily tokens', 'Web search & code execution', 'Built for long-form answers'],
    bestFor: 'Long, detailed explanations (length > reasoning)',
    note: 'Only 250 requests/day — ration it for long answers.'
  },
  'groq/compound': {
    vendor: 'Groq (system)',
    size: 'GPT-OSS 120B + Llama 3.3 70B + tools',
    strengths: ['Unlimited daily tokens', 'Multiple tools per request', 'Long-form answers'],
    bestFor: 'Long, detailed explanations needing tools',
    note: 'Only 250 requests/day — ration it for long answers.'
  },
  'allam-2-7b': {
    vendor: 'SDAIA (open-weight)',
    size: '7B',
    strengths: ['Highest request quota (7,000/day)', 'Decent for short answers'],
    bestFor: 'Many short, simple questions',
    note: 'Weakest reasoning — use only for quick factual checks; low token/min.'
  }
};

// ---------------------------------------------------------------------------
// Intent matrix: map (complexity × length) -> the best model for THAT need.
// The idea is that the student picks HOW HARD the question is and HOW LONG an
// answer they want; we pick the model that fits, then let rotation handle 429s.
//   - Long answers want token-rich models (compound = unlimited TPD).
//   - Many short questions want high-RPD models (allam = 7,000/day).
//   - Hard reasoning wants the strongest model (gpt-oss-120b).
//   - Chinese answers favour Qwen (strongest multilingual on Groq).
// ---------------------------------------------------------------------------
const COMPLEXITY_AXIS = ['simple', 'standard', 'deep'];
const LENGTH_AXIS = ['short', 'medium', 'long'];

const INTENT_MATRIX = {
  simple: {
    short: { model: 'allam-2-7b', reason: 'Quick check — Allam 2 7B has the largest request quota (7,000/day), ideal for many short questions.' },
    medium: { model: 'openai/gpt-oss-20b', reason: 'GPT-OSS 20B is the fastest model on Groq (~1000 tok/s) and good enough for a short explanation.' },
    long: { model: 'groq/compound-mini', reason: 'Compound Mini has unlimited daily tokens — best for a long basic explanation without spending the reasoning models.' }
  },
  standard: {
    short: { model: 'openai/gpt-oss-20b', reason: 'Balanced speed and quality for a typical IB question.' },
    medium: { model: 'qwen/qwen3.8-27b', reason: "Qwen3.8-27B is Groq's strongest general model and best for Chinese; 200K daily tokens." },
    long: { model: 'qwen/qwen3.8-27b', reason: 'Strong reasoning plus 200K daily tokens for a full worked solution.' }
  },
  deep: {
    short: { model: 'openai/gpt-oss-120b', reason: 'GPT-OSS 120B is the top reasoning model — gives a correct short answer with sound method.' },
    medium: { model: 'openai/gpt-oss-120b', reason: 'Best reasoning with 65K max output and 200K daily tokens for a thorough solution.' },
    long: { model: 'openai/gpt-oss-120b', reason: 'Top reasoning with 65K max output fits a long solution; Compound Mini offers unlimited tokens if you need more.' }
  }
};

function resolveIntent(complexity, length) {
  const c = COMPLEXITY_AXIS.includes(complexity) ? complexity : 'standard';
  const l = LENGTH_AXIS.includes(length) ? length : 'medium';
  const pick = INTENT_MATRIX[c]?.[l] || INTENT_MATRIX.standard.medium;
  if (POOL.includes(pick.model)) return pick;
  return { model: POOL[0], reason: 'Recommended model unavailable in this deployment; using best available.' };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dayKey = () => new Date().toISOString().slice(0, 10); // YYYY-MM-DD (UTC)
const estTokens = (s) => Math.ceil(String(s || '').length / 4);

function msUntilUtcMidnight() {
  const now = new Date();
  const midnight = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0));
  return Math.max(1, midnight.getTime() - now.getTime());
}

// ---------------------------------------------------------------------------
// Per-model quota ledger (in-memory; resets at 00:00 UTC)
// ---------------------------------------------------------------------------
const modelState = new Map(); // model -> { day, requests, tokens, blockedUntil, rpmWindow, serverRemaining }

function stateFor(model) {
  const dk = dayKey();
  let s = modelState.get(model);
  if (!s || s.day !== dk) {
    s = { day: dk, requests: 0, tokens: 0, blockedUntil: 0, rpmWindow: [], serverRemaining: null };
    modelState.set(model, s);
  }
  return s;
}

function modelAvailability(model, now = Date.now()) {
  const lim = limitsFor(model);
  const s = stateFor(model);
  if (now < s.blockedUntil) {
    return { ok: false, reason: 'cooldown', retryAfter: Math.ceil((s.blockedUntil - now) / 1000) };
  }
  if (s.serverRemaining !== null && s.serverRemaining <= 0) {
    return { ok: false, reason: 'server_rpd_exhausted', retryAfter: Math.ceil(msUntilUtcMidnight() / 1000) };
  }
  if (s.requests >= lim.rpd) {
    return { ok: false, reason: 'local_rpd', retryAfter: Math.ceil(msUntilUtcMidnight() / 1000) };
  }
  if (s.tokens >= lim.tpd) {
    return { ok: false, reason: 'local_tpd', retryAfter: Math.ceil(msUntilUtcMidnight() / 1000) };
  }
  const recent = s.rpmWindow.filter((t) => now - t < 60_000);
  if (recent.length >= lim.rpm) {
    return { ok: false, reason: 'local_rpm', retryAfter: 60 - Math.floor((now - recent[0]) / 1000) };
  }
  return { ok: true };
}

function orderPool(prefer) {
  const ordered = [];
  if (prefer && POOL.includes(prefer)) ordered.push(prefer);
  for (const m of POOL) if (!ordered.includes(m)) ordered.push(m);
  const now = Date.now();
  // Available models keep their (quality) order and come first; cooling models
  // are kept as a last resort in case everything else is also capped.
  const avail = ordered.filter((m) => modelAvailability(m, now).ok);
  const rest = ordered.filter((m) => !modelAvailability(m, now).ok);
  return [...avail, ...rest];
}

function recordSuccess(model, r) {
  const s = stateFor(model);
  s.requests += 1;
  s.tokens += Number.isFinite(r.billable) ? r.billable : 0; // cached tokens don't count
  if (r.remaining !== null && r.remaining !== undefined && r.remaining !== '') {
    const n = Number(r.remaining);
    if (Number.isFinite(n)) s.serverRemaining = n;
  }
  s.rpmWindow.push(Date.now());
  s.rpmWindow = s.rpmWindow.filter((t) => Date.now() - t < 60_000);
  s.blockedUntil = 0;
}

function markBlocked(model, retryAfter) {
  const s = stateFor(model);
  const wait = Math.max(1, Math.min(Number(retryAfter) || 20, 3600));
  s.blockedUntil = Date.now() + wait * 1000;
  // A long wait means we hit the DAILY cap, not the per-minute one: treat the
  // model as done for the day so rotation moves on instead of hammering it.
  if (wait > 300) s.serverRemaining = 0;
}

// ---------------------------------------------------------------------------
// In-memory response cache (quota saver; ephemeral; privacy-safe)
// Deliberately MODEL-AGNOSTIC: a good answer is reusable no matter which free
// model produced it, which maximises the hit rate and saves the most quota.
// ---------------------------------------------------------------------------
const cache = new Map();
const CACHE_TTL_MS = 1000 * 60 * 60 * 6; // 6 hours
const CACHE_MAX = 500;

function cacheKey(ctxHash, message) {
  return createHash('sha256').update(`${ctxHash}|${message}`).digest('hex');
}
function cacheGet(key) {
  const hit = cache.get(key);
  if (hit && hit.expires > Date.now()) return hit;
  if (hit) cache.delete(key);
  return null;
}
function cacheSet(key, answer, model) {
  if (cache.size >= CACHE_MAX) {
    const firstKey = cache.keys().next().value;
    if (firstKey) cache.delete(firstKey);
  }
  cache.set(key, { expires: Date.now() + CACHE_TTL_MS, answer, model });
}

// ---------------------------------------------------------------------------
// Server-side rate limiter (soft backstop sitting UNDER the pool's aggregate
// capacity, so our friendly message fires before Groq's hard cap would).
// ---------------------------------------------------------------------------
const ipWindows = new Map();
const GLOBAL = { day: 0, dayStart: dayKey() };
const IPC_PER_MIN = Number(process.env.AI_IP_PER_MIN || 15);
const IPC_PER_DAY = Number(process.env.AI_IP_PER_DAY || 300);
const GLOBAL_PER_DAY = Number(process.env.AI_GLOBAL_PER_DAY || 6000);

export function checkRateLimit(ip) {
  const now = Date.now();
  const dk = dayKey();
  if (GLOBAL.dayStart !== dk) {
    GLOBAL.day = 0;
    GLOBAL.dayStart = dk;
  }
  if (GLOBAL.day >= GLOBAL_PER_DAY) {
    return { ok: false, retryAfter: Math.ceil(msUntilUtcMidnight() / 1000), reason: 'global_daily' };
  }
  let w = ipWindows.get(ip);
  if (!w || w.dayStart !== dk) {
    w = { min: [], day: 0, dayStart: dk };
    ipWindows.set(ip, w);
  }
  w.min = w.min.filter((t) => now - t < 60_000);
  if (w.min.length >= IPC_PER_MIN) {
    const wait = 60 - Math.floor((now - w.min[0]) / 1000);
    return { ok: false, retryAfter: Math.max(1, wait), reason: 'ip_per_min' };
  }
  if (w.day >= IPC_PER_DAY) {
    return { ok: false, retryAfter: Math.ceil(msUntilUtcMidnight() / 1000), reason: 'ip_daily' };
  }
  w.min.push(now);
  w.day += 1;
  GLOBAL.day += 1;
  return { ok: true };
}

export class AIError extends Error {
  constructor(code, message, status = 400, retryAfter = null) {
    super(message);
    this.code = code;
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

// ---------------------------------------------------------------------------
// Status / observability (no secrets — model ids and counters only)
// ---------------------------------------------------------------------------
export function aiStatus() {
  const now = Date.now();
  const models = POOL.map((id) => {
    const lim = limitsFor(id);
    const s = stateFor(id);
    const av = modelAvailability(id, now);
    const remaining = s.serverRemaining !== null ? s.serverRemaining : Math.max(0, lim.rpd - s.requests);
    return {
      id,
      label: lim.label,
      cache: lim.cache,
      unknown: Boolean(lim.unknown),
      rpm: lim.rpm,
      rpd: Number.isFinite(lim.rpd) ? lim.rpd : null,
      tpm: Number.isFinite(lim.tpm) ? lim.tpm : null,
      tpd: Number.isFinite(lim.tpd) ? lim.tpd : null, // null = unlimited
      tpdRemaining: Number.isFinite(lim.tpd) ? Math.max(0, lim.tpd - s.tokens) : null, // null = unlimited
      used: s.requests,
      tokensUsed: s.tokens,
      remaining: Number.isFinite(remaining) ? remaining : null,
      available: av.ok,
      reason: av.ok ? null : av.reason,
      retryAfter: av.ok ? null : av.retryAfter || null,
      caps: MODEL_CAPS[id] || null
    };
  });

  const aggregate = {
    models: models.length,
    rpd: models.reduce((a, m) => a + (m.rpd || 0), 0),
    rpdRemaining: models.reduce((a, m) => a + (m.remaining || 0), 0),
    tpd: models.some((m) => m.tpd === null) ? null : models.reduce((a, m) => a + (m.tpd || 0), 0),
    cacheEligibleModels: models.filter((m) => m.cache).length,
    unlimitedTpdModels: models.filter((m) => m.tpd === null).length,
    availableNow: models.filter((m) => m.available).length
  };

  return {
    configured: CONFIGURED,
    model: CONFIGURED ? POOL[0] || null : null,
    maxTokens: MAX_TOKENS,
    pool: models,
    aggregate,
    intentMatrix: {
      complexity: COMPLEXITY_AXIS,
      length: LENGTH_AXIS,
      recommend: INTENT_MATRIX
    },
    resetInSeconds: Math.ceil(msUntilUtcMidnight() / 1000)
  };
}

// ---------------------------------------------------------------------------
// Prompt
//
// STATIC_PROMPT is intentionally large and byte-identical across every call so
// that Groq's automatic prefix cache keeps hitting: cached input tokens do not
// count toward this org's TPM/TPD budget, which effectively enlarges it.
// ---------------------------------------------------------------------------
const STATIC_PROMPT = `You are a patient, precise IB Diploma Programme study assistant embedded in a revision app for Mathematics AA HL, Physics HL, and Computer Science HL.

How to answer:
- Teach the method, not just the result. Work through the reasoning in clear steps, and show the key algebra or physics so the student can reproduce it.
- Prefer step-by-step guidance. Give the final answer as well when the student is clearly checking their work, but always keep the reasoning visible.
- Use the mark allocations: a 5-mark question needs more structure than a 2-mark one.
- Reference the command term when relevant (state, describe, explain, derive, calculate, discuss, evaluate).
- If the student's reasoning is wrong, say precisely where it breaks and why, then show the correct path.

Format:
- Be concise but complete. Short paragraphs and numbered steps beat long prose.
- Write mathematics in LaTeX between $...$ (inline) or $$...$$ (display); the app renders it with KaTeX. Do not wrap LaTeX in code fences.
- Match the language of the student's question (English or Chinese). Keep code, symbols, units, and technical terms in English.
- Never invent context that was not provided. If you are unsure, say so plainly rather than guessing.

Boundaries:
- You only help with IB DP study: Mathematics AA HL, Physics HL, Computer Science HL, and directly related academic skills.
- If asked something outside that scope, briefly redirect to study help.
- Do not produce harmful, unsafe, or non-academic content.`;

function truncate(s, n) {
  s = String(s ?? '');
  return s.length > n ? s.slice(0, n) + '…' : s;
}

// ---------------------------------------------------------------------------
// One model call. Throws AIError('rate_limited') on 429 so the caller rotates.
// ---------------------------------------------------------------------------
async function callModel(model, userContent) {
  const body = {
    model,
    messages: [
      { role: 'system', content: STATIC_PROMPT }, // invariant prefix -> cacheable
      { role: 'user', content: userContent }
    ],
    max_tokens: MAX_TOKENS,
    temperature: 0.3,
    stream: false
  };

  let resp;
  try {
    resp = await fetch(`${GROQ_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${API_KEY}` },
      body: JSON.stringify(body)
    });
  } catch (e) {
    throw new AIError('network', 'Could not reach the AI service.', 502);
  }

  const h = (n) => resp.headers.get(n);
  const remaining = h('x-ratelimit-remaining-requests');
  const limit = h('x-ratelimit-limit-requests');
  const resetsIn = h('x-ratelimit-reset-requests');

  if (resp.status === 429) {
    const retryAfter = Number(h('retry-after')) || 20;
    const err = new AIError('rate_limited', 'Free-model quota hit for this model.', 429, retryAfter);
    err.quotaMeta = { remaining, limit, resetsIn };
    throw err;
  }
  if (resp.status === 401 || resp.status === 403) {
    throw new AIError('auth', 'AI service rejected the API key. Check GROQ_API_KEY on the server.', 500);
  }
  if (!resp.ok) {
    throw new AIError('upstream', `AI service returned an error (${resp.status}).`, 502);
  }

  const data = await resp.json();
  const answer = data?.choices?.[0]?.message?.content?.trim();
  if (!answer) throw new AIError('empty', 'The AI returned an empty response.', 502);

  const usage = data?.usage || {};
  const cachedTokens = Number(usage?.prompt_tokens_details?.cached_tokens || 0);
  const total = Number(usage?.total_tokens || 0);
  // Cached tokens don't count toward the org's rate limits, so only the rest
  // consumes the daily budget.
  const billable = Math.max(0, total - cachedTokens);

  return { answer, remaining, limit, resetsIn, total, cachedTokens, billable, model };
}

function quotaMessage() {
  const msLeft = msUntilUtcMidnight();
  const h = Math.floor(msLeft / 3_600_000);
  const m = Math.max(0, Math.round((msLeft % 3_600_000) / 60_000));
  const local = new Date(Date.now() + msLeft).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return `The free AI quota for today is used up across all models. It refills at 00:00 UTC (in about ${h}h ${m}m, i.e. around ${local} your time). Please try again after that.`;
}

/**
 * Ask the pooled Groq free-tier models, rotating to the next free model on 429.
 * @param {object} opts
 * @param {string} opts.message
 * @param {string} [opts.questionContext]
 * @param {string} [opts.subject]
 * @param {string} [opts.topic]
 * @param {number} [opts.marks]
 * @param {string} [opts.model] explicit preferred model id (overrides intent)
 * @param {string} [opts.complexity] 'simple' | 'standard' | 'deep' (intent)
 * @param {string} [opts.length] 'short' | 'medium' | 'long' (intent)
 */
export async function askAI({ message, questionContext, subject, topic, marks, model: preferModel, complexity, length } = {}) {
  if (!CONFIGURED) {
    throw new AIError('not_configured', 'AI assistant is not configured on the server (set GROQ_API_KEY).', 200);
  }
  if (!message || !String(message).trim()) {
    throw new AIError('empty_message', 'Please enter a question.');
  }

  // Resolve the preferred model: an explicit choice always wins; otherwise the
  // student's (complexity × length) intent picks the best-fit free model.
  let prefer = preferModel;
  if (!prefer) {
    prefer = resolveIntent(complexity, length).model;
  }

  const cleanMessage = truncate(String(message), MAX_MESSAGE_CHARS);
  const ctx = questionContext ? truncate(String(questionContext), MAX_CONTEXT_CHARS) : '';
  const ctxHash = createHash('sha256')
    .update(`${subject || ''}|${topic || ''}|${ctx}`)
    .digest('hex')
    .slice(0, 16);

  // Model-agnostic cache: any good answer is reusable regardless of producer.
  const key = cacheKey(ctxHash, cleanMessage);
  const cached = cacheGet(key);
  if (cached) {
    return { answer: cached.answer, model: cached.model, cached: true, quota: null };
  }

  const userContent = [
    ctx
      ? `Context — an IB DP ${subject || ''} question${topic ? ` (topic: ${topic})` : ''}${marks ? ` [${marks} marks]` : ''}:\n"""\n${ctx}\n"""`
      : '',
    `Student: ${cleanMessage}`
  ]
    .filter(Boolean)
    .join('\n\n');

  const ordered = orderPool(prefer);
  let attempted = 0;
  let lastQuota = null;
  let lastErr = null;

  for (const model of ordered) {
    const av = modelAvailability(model);
    if (!av.ok) continue; // capped/cooldown -> try the next free model
    attempted += 1;

    try {
      const r = await callModel(model, userContent);
      recordSuccess(model, r);
      cacheSet(key, r.answer, model);
      return {
        answer: r.answer,
        model,
        cached: false,
        quota: {
          remaining: r.remaining,
          limit: r.limit,
          resetsIn: r.resetsIn,
          tokensUsed: r.total,
          cachedTokens: r.cachedTokens
        }
      };
    } catch (e) {
      if (e instanceof AIError && e.code === 'auth') throw e; // bad key: stop
      if (e instanceof AIError && e.code === 'rate_limited') {
        markBlocked(model, e.retryAfter);
        lastQuota = e;
        continue; // rotate to the next free model — no sleeping, no paying
      }
      lastErr = e; // network/upstream/empty: try another model too
      continue;
    }
  }

  // Nothing left: either every model was already capped, or every attempt 429'd.
  if (attempted === 0 || lastQuota) {
    return {
      answer: quotaMessage(),
      model: null,
      cached: false,
      error: 'quota_exceeded',
      quota: { poolExhausted: true, resetsInSeconds: Math.ceil(msUntilUtcMidnight() / 1000) }
    };
  }
  if (lastErr) throw lastErr;
  throw new AIError('unknown', 'AI request failed.', 502);
}

export default { askAI, aiStatus, checkRateLimit, AIError };
