import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { CollectionSummary, KnowledgePoint } from './types';
import { getCollections, getFavorites, getKnowledgePoints, toggleFavorite as apiToggleFav, addToCollection as apiAddToCollection, createCollection as apiCreateCollection } from './api';

interface AppState {
  favorites: Record<string, true>;
  collections: CollectionSummary[];
  kpList: KnowledgePoint[];
  kpMap: Record<string, KnowledgePoint>;
  toggleFav: (id: string) => Promise<void>;
  addToCollection: (collectionId: string, qid: string) => Promise<void>;
  createCollection: (name: string) => Promise<string>;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [favorites, setFavorites] = useState<Record<string, true>>({});
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [kpList, setKpList] = useState<KnowledgePoint[]>([]);

  const refresh = useCallback(async () => {
    try {
      const [fav, cols, kps] = await Promise.all([
        getFavorites().catch(() => []),
        getCollections().catch(() => []),
        getKnowledgePoints().catch(() => [])
      ]);
      const fmap: Record<string, true> = {};
      fav.forEach((q) => { fmap[q.id] = true; });
      setFavorites(fmap);
      setCollections(cols);
      setKpList(kps);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const toggleFav = useCallback(async (id: string) => {
    const r = await apiToggleFav(id);
    setFavorites((prev) => {
      const next = { ...prev };
      if (r.favorited) next[id] = true; else delete next[id];
      return next;
    });
  }, []);

  const addToCollection = useCallback(async (collectionId: string, qid: string) => {
    await apiAddToCollection(collectionId, qid);
    refresh();
  }, [refresh]);

  const createCollection = useCallback(async (name: string) => {
    const { id } = await apiCreateCollection(name);
    refresh();
    return id;
  }, [refresh]);

  const kpMap: Record<string, KnowledgePoint> = {};
  kpList.forEach((k) => { kpMap[k.id] = k; });

  return (
    <Ctx.Provider value={{ favorites, collections, kpList, kpMap, toggleFav, addToCollection, createCollection, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAppState(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAppState must be used within AppStateProvider');
  return v;
}
