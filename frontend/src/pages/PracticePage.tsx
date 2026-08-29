import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getCollection, getQuestions, recordAttempt } from '../api';
import { useAppState } from '../state';
import type { Question, QuestionQuery } from '../types';
import RichText from '../components/RichText';

export default function PracticePage() {
  const [searchParams] = useSearchParams();
  const collectionId = searchParams.get('collection');
  const { kpList } = useAppState();

  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [paper_type, setPaperType] = useState('');
  const [selectedKps, setSelectedKps] = useState<string[]>([]);
  const [category, setCategory] = useState<'all' | 'book' | 'past' | 'topic' | 'questionbank'>('all');
  const [limit, setLimit] = useState(10);
  const [attempted, setAttempted] = useState(false);

  const [quiz, setQuiz] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [correct, setCorrect] = useState(0);
  const [running, setRunning] = useState(false);

  const [collectionItems, setCollectionItems] = useState<Question[] | null>(null);
  const [collectionName, setCollectionName] = useState('');

  useEffect(() => {
    if (collectionId) {
      getCollection(collectionId).then((d) => {
        setCollectionItems(d.items);
        setCollectionName(d.collection.name);
      }).catch(() => setCollectionItems([]));
    } else {
      setCollectionItems(null);
      setCollectionName('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionId]);

  async function start() {
    const params: QuestionQuery = {
      subject, topic, paper_type,
      knowledge_point: selectedKps.join(',') || undefined,
      category, limit, offset: 0
    };
    const r = await getQuestions(params);
    setQuiz(r.items);
    setIdx(0); setRevealed(false); setCorrect(0); setRunning(true);
    setAttempted(true);
  }

  function startCollection() {
    if (!collectionItems) return;
    setQuiz(collectionItems);
    setIdx(0); setRevealed(false); setCorrect(0); setRunning(true);
  }

  function finish() { setRunning(false); setQuiz([]); setAttempted(false); }

  async function mark(status: 'correct' | 'incorrect') {
    const q = quiz[idx];
    if (q) {
      await recordAttempt({ question_id: q.id, result: status }).catch(() => {});
      if (status === 'correct') setCorrect((c) => c + 1);
    }
    if (idx + 1 >= quiz.length) { setRevealed(true); return; }
    setIdx(idx + 1);
    setRevealed(false);
  }

  function toggleKp(id: string) {
    setSelectedKps((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  }

  if (running && quiz.length > 0) {
    const q = quiz[idx];
    const done = idx >= quiz.length;
    if (done) {
      return (
        <div className="practice-end">
          <h2>Quiz complete</h2>
          <p>You answered <b>{correct}</b> / {quiz.length} correctly.</p>
          <button className="primary" onClick={finish}>Back to setup</button>
        </div>
      );
    }
    return (
      <div className="practice">
        <div className="practice-progress">Question {idx + 1} / {quiz.length} · score {correct}</div>
        <div className="card">
          <div className="card-meta">
            <span className="badge">{q.subject}</span>
            {q.topic && <span className="badge">{q.topic}</span>}
            {q.marks != null && <span className="badge">[{q.marks} marks]</span>}
          </div>
          <div className="card-q"><RichText text={q.question} /></div>
          {revealed && (
            <div className="card-answer">
              <div className="answer-label">Answer</div>
              <div className="answer-body"><RichText text={q.answer} /></div>
              <div className="answer-label">Explanation</div>
              <div className="answer-body"><RichText text={q.explanation} /></div>
            </div>
          )}
        </div>
        <div className="practice-controls">
          {!revealed ? (
            <button className="primary" onClick={() => setRevealed(true)}>Reveal answer</button>
          ) : (
            <>
              <button className="secondary" onClick={() => mark('incorrect')}>I was wrong</button>
              <button className="primary" onClick={() => mark('correct')}>I was right</button>
            </>
          )}
        </div>
      </div>
    );
  }

  if (collectionId) {
    return (
      <div className="practice-setup">
        <Link className="backlink" to="/practice">← Normal practice</Link>
        <h3>Practice set: {collectionName || '…'}</h3>
        <p className="muted">{collectionItems ? `${collectionItems.length} question(s) in this set.` : 'Loading…'}</p>
        <button className="primary" disabled={!collectionItems || collectionItems.length === 0} onClick={startCollection}>Start set quiz</button>
      </div>
    );
  }

  return (
    <div className="practice-setup">
      <h3>Practice setup</h3>
      <label>Subject
        <select value={subject} onChange={(e) => setSubject(e.target.value)}>
          <option value="">All</option>
          {['CS', 'Math', 'Physics'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <label>Topic
        <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="free text topic" />
      </label>
      <label>Paper
        <select value={paper_type} onChange={(e) => setPaperType(e.target.value)}>
          <option value="">All</option>
          {['Paper 1', 'Paper 2', 'Paper 3'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <div className="filter-group">
        <span className="filter-label">Category</span>
        <div className="seg">
          <button className={'seg-btn' + (category === 'all' ? ' on' : '')} onClick={() => setCategory('all')}>All</button>
          <button className={'seg-btn' + (category === 'book' ? ' on' : '')} onClick={() => setCategory('book')}>Books</button>
          <button className={'seg-btn' + (category === 'past' ? ' on' : '')} onClick={() => setCategory('past')}>Past papers</button>
          <button className={'seg-btn' + (category === 'topic' ? ' on' : '')} onClick={() => setCategory('topic')}>Topic questions</button>
          <button className={'seg-btn' + (category === 'questionbank' ? ' on' : '')} onClick={() => setCategory('questionbank')}>Question bank</button>
        </div>
      </div>
      <div className="kp-pick">
        <div className="kp-pick-title">Knowledge points (optional)</div>
        <div className="kp-chips">
          {kpList.map((k) => (
            <button key={k.id}
              className={'kp-chip' + (selectedKps.includes(k.id) ? ' active' : '')}
              onClick={() => toggleKp(k.id)}>
              {k.code} {k.title}
            </button>
          ))}
        </div>
      </div>
      <label>Number of questions
        <input type="number" value={limit} min={1} max={50} onChange={(e) => setLimit(Number(e.target.value))} />
      </label>
      <button className="primary" onClick={start}>Start quiz</button>
      {attempted && quiz.length === 0 && (
        <div className="empty"><p className="muted">No questions match these filters. Try a different subject / topic / paper, or choose the “All” category.</p></div>
      )}
    </div>
  );
}
