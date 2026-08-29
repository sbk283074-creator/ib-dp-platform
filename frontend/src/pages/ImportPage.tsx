import { useState } from 'react';
import { importQuestions } from '../api';

const TEMPLATE = `{
  "questions": [
    {
      "id": "cs-1-1",
      "subject": "CS",
      "level": "HL",
      "topic": "System fundamentals",
      "subtopic": "System lifecycle",
      "paper_type": "Paper 1",
      "command_term": "Outline",
      "marks": 4,
      "difficulty": 2,
      "question": "Outline the stages of the system lifecycle.",
      "answer": "Investigation, analysis, design, development, testing, implementation, maintenance.",
      "explanation": "Each phase has deliverables that feed the next.",
      "source": "original (IB-style)",
      "tags": ["system lifecycle"]
    }
  ]
}`;

export default function ImportPage() {
  const [text, setText] = useState('');
  const [result, setResult] = useState<{ inserted: number; total: number; errors: any[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function loadFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result || ''));
    reader.readAsText(file);
  }

  function downloadTemplate() {
    const blob = new Blob([TEMPLATE], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'questions.template.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  async function doImport() {
    setError('');
    setResult(null);
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (e) {
      setError('Invalid JSON: ' + (e as Error).message);
      return;
    }
    const arr = Array.isArray(parsed) ? parsed : parsed.questions;
    if (!Array.isArray(arr)) {
      setError('Expected a JSON array, or an object with a "questions" array.');
      return;
    }
    setBusy(true);
    try {
      const r = await importQuestions(arr);
      setResult(r);
    } catch (e) {
      setError('Import failed: ' + (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="import-page">
      <h3>Batch import questions</h3>
      <p className="muted">
        Upload or paste a JSON file of questions. Re-importing the same file updates existing
        rows (match by <code>id</code>). Large files are also supported via the CLI:
        <br />
        <code>cd backend &amp;&amp; npm run import ../path/questions.json</code>
      </p>

      <div className="import-controls">
        <input type="file" accept="application/json,.json" onChange={(e) => e.target.files && loadFile(e.target.files[0])} />
        <button className="secondary" onClick={downloadTemplate}>Download template</button>
        <button className="primary" onClick={doImport} disabled={busy || text.trim() === ''}>
          {busy ? 'Importing…' : 'Import questions'}
        </button>
      </div>

      <textarea
        className="import-textarea"
        placeholder="Paste JSON here, or use the file picker above…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
      />

      {error && <div className="import-error">⚠ {error}</div>}

      {result && (
        <div className={'import-result' + (result.errors.length ? ' with-errors' : '')}>
          <b>Imported {result.inserted}</b> of {result.total} question(s).
          {result.errors.length > 0 && (
            <>
              <div className="import-errhead">{result.errors.length} skipped:</div>
              <ul className="import-errlist">
                {result.errors.slice(0, 20).map((e, i) => (
                  <li key={i}>{e.index != null ? `[#${e.index}] ` : ''}{e.error}{e.id ? ` (id=${e.id})` : ''}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
