#!/usr/bin/env node
'use strict';
/**
 * fix_question_format.cjs
 * Safe, conservative formatting fixes for question/answer text in the IB DP bank.
 *
 * Fixes applied:
 *  1. Join consecutive numeric-only lines (4+ in a row) → space-joined single line
 *     e.g. 5\n4\n3\n2\n1\n0 → "5 4 3 2 1 0"
 *  2. Join consecutive bracketed-only lines (3+ in a row, e.g. [0] [1] [2])
 *     → space-joined, e.g. "[0] [1] [2] [3]"
 *  3. Split long single-line paragraphs (>250 chars, 1 non-empty line)
 *     Split points (in order):
 *     - After [N] marks indicator (e.g. ". [2]" → ". [2]\n")
 *     - Before "(This question continues" / "(Question N continued"
 *     - After ". " followed by an IB command term (Calculate, Determine, Explain, ...)
 *     - After ". " followed by uppercase letter (only for lines still >300 chars)
 *  4. Merge "A." or "B." etc. with the next line if the next line is the option value
 *     (fixes MCQ where "A." is on one line and the value on the next)
 *
 * NOT applied (too many false positives):
 * - Adding newlines before [N] marks (standard IB format: [N] at end of line)
 * - Adding newlines before a./b./c. labels (false positives with unit abbreviations)
 *
 * Output: writes a preview JSON + summary to stdout.
 * Usage: node fix_question_format.cjs --dry-run    (preview only, no DB write)
 *        node fix_question_format.cjs              (apply to DB)
 */

const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'data', 'app.db');
const db = new Database(DB_PATH);

// ─── Config ───────────────────────────────────────────────

// IB command terms — when preceded by ". " or "] ", split before them
const COMMAND_TERMS = [
  'Calculate', 'Determine', 'Explain', 'State', 'Outline', 'Describe',
  'Identify', 'Define', 'Show', 'Find', 'Write', 'Draw', 'Sketch',
  'Construct', 'Suggest', 'Deduce', 'Hence', 'Using', 'Consider',
  'Analyse', 'Analyze', 'Compare', 'Evaluate', 'Justify', 'Predict',
  'Apply', 'Formulate', 'Derive', 'Solve', 'Prove', 'Demonstrate',
  'Copy', 'Complete', 'Convert', 'Estimate', 'Give', 'Label', 'List',
  'Plot', 'Represent', 'Comment', 'Discuss', 'Summarise', 'Summarize',
  'Translate', 'Research', 'Starting', 'Award', 'Accept', 'Note'
];

// Common abbreviations that end with "." — don't split after these
const ABBREVIATIONS = new Set([
  'Mr', 'Mrs', 'Ms', 'Dr', 'St', 'Prof', 'Sr', 'Jr',
  'vs', 'etc', 'approx', 'fig', 'ex', 'eg', 'ie', 'cf',
  'al', 'max', 'min', 'inf', 'nan', 'No'
]);

// ─── Helpers ──────────────────────────────────────────────

function isNumericOnly(line) {
  const t = line.trim();
  if (!t) return false;
  // Pure number (int, decimal, negative): 5, 3.5, -1, 0.8, 100
  // Also match Unicode minus (− U+2212) and en-dash (– U+2013)
  return /^[−–\-]?[\d.]+$/.test(t) && t.length <= 6;
}

function isSimpleBracket(line) {
  // [0], [1], [2] — bracketed short content, no text outside brackets
  const t = line.trim();
  return /^\[[\d\s\w]{0,15}\]$/.test(t);
}

// ─── Fix 1: Join consecutive numeric-only lines ───────────

function fixConsecutiveNumericLines(text) {
  const lines = text.split('\n');
  const result = [];
  let i = 0;
  let changed = false;

  while (i < lines.length) {
    if (isNumericOnly(lines[i])) {
      let run = [];
      while (i < lines.length && isNumericOnly(lines[i])) {
        run.push(lines[i].trim());
        i++;
      }
      if (run.length >= 3) {
        result.push(run.join(' '));
        changed = true;
      } else {
        result.push(...run);
      }
    } else {
      result.push(lines[i]);
      i++;
    }
  }

  return { text: result.join('\n'), changed };
}

// ─── Fix 2: Join consecutive bracketed-only lines ─────────

function fixConsecutiveBracketedLines(text) {
  const lines = text.split('\n');
  const result = [];
  let i = 0;
  let changed = false;

  while (i < lines.length) {
    if (isSimpleBracket(lines[i])) {
      let run = [];
      while (i < lines.length && isSimpleBracket(lines[i])) {
        run.push(lines[i].trim());
        i++;
      }
      if (run.length >= 3) {
        result.push(run.join(' '));
        changed = true;
      } else {
        result.push(...run);
      }
    } else {
      result.push(lines[i]);
      i++;
    }
  }

  return { text: result.join('\n'), changed };
}

// ─── Fix 3: Split long single-line paragraphs ──────────────

function splitLongParagraph(text) {
  const lines = text.split('\n');
  const nonEmpty = lines.filter(l => l.trim().length > 0);

  // Only process single-line paragraphs > 250 chars
  if (nonEmpty.length !== 1 || nonEmpty[0].length < 250) {
    return { text, changed: false };
  }

  let line = nonEmpty[0];
  let parts = [line];

  // 3a: Insert newline after [N] marks when followed by more text
  parts = parts.flatMap(p => {
    return p.replace(/(\[\d+\])\s+(?=\S)/g, '$1\n').split('\n');
  });

  // 3b: Insert newline before continuation markers
  parts = parts.flatMap(p => {
    return p.replace(/\s*\((This question continues[^)]*)\)\s*/g, '\n($1)\n')
            .replace(/\s*\((Question \d+ continued)\)\s*/g, '\n($1)\n')
            .split('\n');
  });

  // 3c: Insert newline after ". " before IB command terms
  parts = parts.flatMap(p => {
    let result = p;
    for (const term of COMMAND_TERMS) {
      const re = new RegExp('[.\\]]\\s+(' + term + ')\\b', 'g');
      result = result.replace(re, match => match.replace(/\s+/, '\n'));
    }
    return result.split('\n');
  });

  // 3d: For lines still > 300 chars, split at ". " before uppercase (check abbreviations)
  parts = parts.flatMap(p => {
    if (p.length > 300) {
      // Use regex to find ". " before uppercase, then split
      const segments = [];
      let lastEnd = 0;
      const regex = /\.\s+(?=[A-Z])/g;
      let match;
      while ((match = regex.exec(p)) !== null) {
        // Check if the word before "." is an abbreviation
        const beforeText = p.substring(lastEnd, match.index);
        const lastWord = beforeText.trim().split(/\s+/).pop();
        const cleaned = lastWord ? lastWord.replace(/[.,;:!?]$/, '') : '';
        if (cleaned && ABBREVIATIONS.has(cleaned)) {
          continue; // Don't split here
        }
        segments.push(p.substring(lastEnd, match.index + 1).trim()); // include the "."
        lastEnd = match.index + 1 + match[0].length - 1; // after ". "
      }
      segments.push(p.substring(lastEnd).trim());
      return segments.filter(s => s.length > 0);
    }
    return [p];
  });

  // Clean up
  parts = parts.map(p => p.trim()).filter(p => p.length > 0);

  const newText = parts.join('\n');
  return { text: newText, changed: newText !== text };
}

// ─── Fix 4: Merge broken MCQ options (A.\n value → A. value) ──

function fixBrokenMCQOptions(text) {
  const lines = text.split('\n');
  const result = [];
  let changed = false;
  let i = 0;

  while (i < lines.length) {
    // Check if this line is just "A." or "B." etc. (with optional trailing space)
    const mcqMatch = lines[i].trim().match(/^([A-D])\.\s*$/);
    if (mcqMatch && i + 1 < lines.length) {
      const nextLine = lines[i + 1].trim();
      // Only merge if next line is a short option value (≤ 15 chars),
      // doesn't start with "(" (sub-question), uppercase letter+lowercase (sentence),
      // or an MCQ label itself (A. B. C. D.)
      if (nextLine.length > 0 && nextLine.length <= 15
          && !nextLine.startsWith('(')
          && !/^[A-Z][a-z]/.test(nextLine)
          && !/^[A-D]\./.test(nextLine)) {
        result.push(`${mcqMatch[1]}. ${nextLine}`);
        i += 2; // skip next line
        changed = true;
        continue;
      }
    }
    result.push(lines[i]);
    i++;
  }

  return { text: result.join('\n'), changed };
}

// ─── Apply all fixes ──────────────────────────────────────

function applyAllFixes(originalText) {
  if (!originalText) return { text: originalText, changes: [] };

  let text = originalText;
  let changes = [];

  // Fix 1: Join consecutive numeric lines
  let r1 = fixConsecutiveNumericLines(text);
  if (r1.changed) { text = r1.text; changes.push('join_numeric_lines'); }

  // Fix 2: Join consecutive bracketed lines
  let r2 = fixConsecutiveBracketedLines(text);
  if (r2.changed) { text = r2.text; changes.push('join_bracketed_lines'); }

  // Fix 3: Split long paragraphs
  let r3 = splitLongParagraph(text);
  if (r3.changed) { text = r3.text; changes.push('split_long_para'); }

  // Fix 4: Fix broken MCQ options
  let r4 = fixBrokenMCQOptions(text);
  if (r4.changed) { text = r4.text; changes.push('fix_mcq_options'); }

  return { text, changes };
}

// ─── Main ─────────────────────────────────────────────────

const dryRun = !process.argv.includes('--apply');
console.log(`Mode: ${dryRun ? 'DRY RUN (preview)' : 'APPLY TO DB'}`);
console.log(`DB: ${DB_PATH}\n`);

const subjects = ['CS', 'Math AA HL', 'Physics'];
let totalChanged = 0;
let totalQuestions = 0;
let changeLog = [];
let fixTypeCounts = {};

for (const subj of subjects) {
  const rows = db.prepare("SELECT id, question, answer FROM questions WHERE subject = ?").all(subj);
  let subjChanged = 0;
  let subjFixTypes = {};

  for (const q of rows) {
    totalQuestions++;
    let questionChanged = false;
    let answerChanged = false;
    let qChanges = [];
    let aChanges = [];

    const qResult = applyAllFixes(q.question);
    if (qResult.text !== q.question) {
      questionChanged = true;
      qChanges = qResult.changes;
    }

    let newAnswer = q.answer;
    if (q.answer) {
      const aResult = applyAllFixes(q.answer);
      if (aResult.text !== q.answer) {
        answerChanged = true;
        aChanges = aResult.changes;
        newAnswer = aResult.text;
      }
    }

    if (questionChanged || answerChanged) {
      subjChanged++;
      totalChanged++;
      const allChanges = [...qChanges, ...aChanges];
      for (const c of allChanges) {
        fixTypeCounts[c] = (fixTypeCounts[c] || 0) + 1;
        subjFixTypes[c] = (subjFixTypes[c] || 0) + 1;
      }

      // Log all changes for preview
      if (changeLog.length < 100) {
        changeLog.push({
          id: q.id,
          subject: subj,
          changes: allChanges,
          beforeQ: q.question,
          afterQ: qResult.text,
          beforeA: q.answer,
          afterA: newAnswer,
        });
      }

      if (!dryRun) {
        const stmt = db.prepare("UPDATE questions SET question = ?, answer = ? WHERE id = ?");
        stmt.run(qResult.text, newAnswer, q.id);
      }
    }
  }

  console.log(`${subj}: ${subjChanged} / ${rows.length} questions changed`);
  for (const [fix, count] of Object.entries(subjFixTypes)) {
    console.log(`  ${fix}: ${count}`);
  }
}

console.log('\n' + '='.repeat(60));
console.log(`TOTAL: ${totalChanged} / ${totalQuestions} questions changed`);
console.log('\nFix type counts:');
for (const [fix, count] of Object.entries(fixTypeCounts).sort((a, b) => b[1] - a[1])) {
  console.log(`  ${fix}: ${count}`);
}

// Write full preview
const previewPath = path.join(__dirname, 'format_fix_preview.json');
fs.writeFileSync(previewPath, JSON.stringify(changeLog, null, 2));
console.log(`\nPreview written to: ${previewPath} (${changeLog.length} entries)`);

if (dryRun) {
  console.log('\n*** DRY RUN — no changes written to DB. Run with --apply to commit. ***');
} else {
  console.log('\n*** Changes applied to DB. ***');
}
