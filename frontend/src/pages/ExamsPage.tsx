import { useEffect, useMemo, useState } from 'react';
import { deleteExam, exportHtml, generateExam, getExam, getExams, getPaperTemplates } from '../api';
import type { ExamPaper, PaperTemplate } from '../types';
import RichText from '../components/RichText';

export default function ExamsPage() {
  const [templates, setTemplates] = useState<PaperTemplate[]>([]);
  const [exams, setExams] = useState<ExamPaper[]>([]);
  const [selected, setSelected] = useState<ExamPaper | null>(null);

  const [subject, setSubject] = useState('Physics');
  const [templateId, setTemplateId] = useState('');
  const [includeUsed, setIncludeUsed] = useState(false);
  const [authoredFilter, setAuthoredFilter] = useState<'all' | 'ai' | 'real'>('all');
  const [overrideMarks, setOverrideMarks] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  async function refresh() {
    getExams().then(setExams).catch(() => {});
  }
  useEffect(() => {
    getPaperTemplates().then((ts) => {
      setTemplates(ts);
      const first = ts.filter((t) => t.subject === 'Physics');
      if (first.length) setTemplateId(first[0].id);
    }).catch(() => {});
    refresh();
  }, []);

  const subjects = useMemo(() => [...new Set(templates.map((t) => t.subject))], [templates]);
  const filtered = useMemo(() => templates.filter((t) => t.subject === subject), [templates, subject]);

  function onSubjectChange(s: string) {
    setSubject(s);
    const list = templates.filter((t) => t.subject === s);
    if (list.length) setTemplateId(list[0].id);
  }

  async function onGenerate() {
    setError(''); setMsg('');
    if (!templateId) { setError('Pick a paper template first.'); return; }
    setGenerating(true);
    try {
      const exam = await generateExam({
        template_id: templateId,
        include_used: includeUsed,
        authored_filter: authoredFilter,
        override_marks: overrideMarks ? Number(overrideMarks) : undefined
      });
      setSelected(exam);
      setMsg(`Paper generated: ${exam.num_questions} questions · ${exam.total_marks} marks. All questions in it are now marked as used and won't be re-picked by default.`);
      refresh();
    } catch (e: any) {
      setError(e.message || 'Generation failed.');
    } finally {
      setGenerating(false);
    }
  }

  async function openExam(id: string) {
    setSelected(await getExam(id).catch(() => null));
  }
  async function onDelete(id: string) {
    await deleteExam(id).catch(() => {});
    if (selected?.id === id) setSelected(null);
    refresh();
  }
  async function onExport() {
    if (!selected?.items) return;
    const r = await exportHtml(selected.items.map((q) => q.id)).catch(() => null);
    if (!r) return;
    const w = window.open('');
    if (w) { w.document.write(r.html); w.document.close(); }
  }

  return (
    <div className="exams">
      <div className="wrongbook-head">
        <h3>Mock Exam Papers</h3>
      </div>
      <p className="muted">
        Randomly compose a realistic IB mock paper from the question bank. Questions picked for a paper are marked as
        <em> used</em> (with a timestamp) and are excluded from future auto-composition — unless you allow re-using them.
      </p>

      <div className="panel">
        <div className="panel-title">Generate a paper</div>
        <div className="gen-row">
          <label>Subject
            <select value={subject} onChange={(e) => onSubjectChange(e.target.value)}>
              {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label>Template
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              {filtered.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.paper_type} — {t.duration_min} min / {t.total_marks} marks
                  {t.calculator ? ' · calculator' : ''}
                </option>
              ))}
            </select>
          </label>
          <label>Target marks
            <input type="number" value={overrideMarks} placeholder="default" onChange={(e) => setOverrideMarks(e.target.value)} />
          </label>
          <label className="chk">
            <input type="checkbox" checked={includeUsed} onChange={(e) => setIncludeUsed(e.target.checked)} />
            allow re-using used questions
          </label>
          <label>Question source
            <select value={authoredFilter} onChange={(e) => setAuthoredFilter(e.target.value as 'all' | 'ai' | 'real')}>
              <option value="all">All questions</option>
              <option value="ai">AI-generated only</option>
              <option value="real">Real past-paper only</option>
            </select>
          </label>
          <button className="primary" onClick={onGenerate} disabled={generating || !templateId}>
            {generating ? 'Composing…' : 'Generate'}
          </button>
        </div>
        {filtered.find((t) => t.id === templateId) && (
          <div className="muted tpl-desc">{filtered.find((t) => t.id === templateId)!.description}</div>
        )}
        {error && <div className="err">{error}</div>}
        {msg && <div className="ok">{msg}</div>}
      </div>

      {selected && (
        <div className="panel exam-detail">
          <div className="panel-title">
            {selected.name}
            <span className="muted"> · {selected.subject} {selected.paper_type} · {selected.duration_min} min</span>
            <button className="secondary right" onClick={onExport} disabled={!selected.items?.length}>Export / Print</button>
            <button className="secondary right" onClick={() => setSelected(null)}>Close</button>
          </div>
          <div className="muted">
            Created {new Date(selected.created_at).toLocaleString()} · {selected.num_questions} questions ·{' '}
            {selected.total_marks} marks{selected.note ? ` · ${selected.note}` : ''}
          </div>
          <ol className="exam-items">
            {selected.items?.map((q, i) => (
              <li key={q.id} className="exam-item">
                <div className="exam-item-head">
                  <span className="badge">Q{i + 1}</span>
                  {q.marks != null && <span className="badge">[{q.marks} marks]</span>}
                  {q.topic && <span className="badge">{q.topic}</span>}
                  {q.authored_by === 'ai' && <span className="badge ai-badge">AI</span>}
                  {q.source && <span className="muted src">{q.source}</span>}
                </div>
                <div className="card-q"><RichText text={q.question} /></div>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="panel">
        <div className="panel-title">Generated papers</div>
        {exams.length === 0 ? (
          <p className="muted">No papers generated yet.</p>
        ) : (
          <table className="tbl">
            <thead>
              <tr><th>Name</th><th>Subject</th><th>Paper</th><th>Q</th><th>Marks</th><th>Created</th><th></th></tr>
            </thead>
            <tbody>
              {exams.map((e) => (
                <tr key={e.id}>
                  <td>{e.name}</td>
                  <td>{e.subject}</td>
                  <td>{e.paper_type}</td>
                  <td>{e.item_count}</td>
                  <td>{e.total_marks}</td>
                  <td>{new Date(e.created_at).toLocaleString()}</td>
                  <td className="rowbtns">
                    <button className="secondary" onClick={() => openExam(e.id)}>View</button>
                    <button className="secondary danger" onClick={() => onDelete(e.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
