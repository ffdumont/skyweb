import { openDB, type IDBPDatabase } from "idb";

const DB_NAME = "skyweb-tiles";
const STORE_NAME = "tiles";
const DB_VERSION = 1;

interface TileCacheEntry {
  key: string;
  data: object;
  cycle: string;
  timestamp: number;
}

let dbPromise: Promise<IDBPDatabase> | null = null;

function getDb(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "key" });
        }
      },
    });
  }
  return dbPromise;
}

function tileKey(cycle: string, layer: string, z: number, x: number, y: number): string {
  return `${cycle}/${layer}/${z}/${x}/${y}`;
}

export async function getCachedTile(
  cycle: string,
  layer: string,
  z: number,
  x: number,
  y: number,
): Promise<object | null> {
  const db = await getDb();
  const entry = await db.get(STORE_NAME, tileKey(cycle, layer, z, x, y));
  return (entry as TileCacheEntry | undefined)?.data ?? null;
}

export async function cacheTile(
  cycle: string,
  layer: string,
  z: number,
  x: number,
  y: number,
  data: object,
): Promise<void> {
  const db = await getDb();
  const entry: TileCacheEntry = {
    key: tileKey(cycle, layer, z, x, y),
    data,
    cycle,
    timestamp: Date.now(),
  };
  await db.put(STORE_NAME, entry);
}

export async function clearOldCycles(currentCycle: string): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(STORE_NAME, "readwrite");
  const store = tx.objectStore(STORE_NAME);
  let cursor = await store.openCursor();
  while (cursor) {
    const entry = cursor.value as TileCacheEntry;
    if (entry.cycle !== currentCycle) {
      await cursor.delete();
    }
    cursor = await cursor.continue();
  }
  await tx.done;
}
