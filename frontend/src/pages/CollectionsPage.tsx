import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { createCollection, deleteCollection, exportHtml, getCollection, getCollections, removeFromCollection } from '../api';
import type { CollectionDetail, CollectionSummary, Question } from '../types';
import QuestionCard from '../components/QuestionCard';

export default function CollectionsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [list, setList] = useState<CollectionSummary[]>([]);
  const [detail, setDetail] = useState<CollectionDetail | null>(null);
  const [newName, setNewName] = useState('');
  const [loading, setLoading] = useState(false);

  async function refreshList() {
    try { setList(await getCollections()); } catch { /* ignore */ }
  }
  useEffect(() => { refreshList(); }, []);

  useEffect(() => {
    if (!id) { setDetail(null); return; }
    setLoading(true);
    getCollection(id).then(setDetail).catch(() => setDetail(null)).finally(() => setLoading(false));
  }, [id]);

  async function create() {
    const name = newName.trim();
    if (!name) return;
    const { id: newId } = await createCollection(name).catch(() => ({ id: null }));
    setNewName('');
    if (newId) navigate(`/collections/${newId}`);
    else refreshList();
  }
  async function onDelete(cid: string) {
    await deleteCollection(cid).catch(() => {});
    refreshList();
  }
  async function onRemoveItem(qid: string) {
    if (!detail) return;
    await removeFromCollection(detail.collection.id, qid).catch(() => {});
    setDetail({ ...detail, items: detail.items.filter((q) => q.id !== qid) });
  }
  async function onExport() {
    if (!detail) return;
    const r = await exportHtml(detail.items.map((q) => q.id)).catch(() => null);
    if (!r) return;
    const w = window.open('');
    if (w) { w.document.write(r.html); w.document.close(); }
  }

  if (id && detail) {
    return (
      <div className="collection-detail">
        <Link className="backlink" to="/collections">← All collections</Link>
        <div className="collection-head">
          <h3>{detail.collection.name}</h3>
          <div className="collection-actions">
            <button className="primary" onClick={() => navigate(`/practice?collection=${detail.collection.id}`)} disabled={detail.items.length === 0}>
              Practice set
            </button>
            <button className="secondary" onClick={onExport} disabled={detail.items.length === 0}>Export / Print</button>
            {detail.collection.id !== 'default-favorites' && (
              <button className="danger" onClick={() => onDelete(detail.collection.id)}>Delete set</button>
            )}
          </div>
        </div>
        {loading ? <p className="muted">Loading…</p> :
          detail.items.length === 0 ? (
            <div className="empty"><p className="muted">This collection is empty. Use ⊕ on any question to add it.</p></div>
          ) : (
            <div className="results">
              {detail.items.map((q: Question) => (
                <div key={q.id} className="col-item">
                  <QuestionCard q={q} />
                  <button className="linkbtn danger-text" onClick={() => onRemoveItem(q.id)}>Remove from set</button>
                </div>
              ))}
            </div>
          )}
      </div>
    );
  }

  return (
    <div className="collections">
      <h3>Collections</h3>
      <div className="collection-new">
        <input placeholder="New collection name (e.g. ‘2025 Paper 1 mock’)" value={newName}
          onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') create(); }} />
        <button className="primary" onClick={create} disabled={!newName.trim()}>Create</button>
      </div>
      {list.length === 0 ? (
        <div className="empty"><p className="muted">No collections yet. Create one, then add questions with the ⊕ button.</p></div>
      ) : (
        <div className="col-grid">
          {list.map((c) => (
            <div key={c.id} className="col-card">
              <Link to={`/collections/${c.id}`} className="col-card-name">{c.name}
                {c.id === 'default-favorites' && <span className="badge book-badge">★ 快捷收藏</span>}
              </Link>
              <div className="col-card-meta">{c.item_count} question(s)</div>
              {c.id !== 'default-favorites' && (
                <button className="linkbtn danger-text" onClick={() => onDelete(c.id)}>Delete</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
