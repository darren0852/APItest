export interface PublicModelCacheItem {
  model: string;
  input_sell: number;
  output_sell: number;
  cache_write_sell: number;
  cache_read_sell: number;
  official?: [number, number, number, number] | null;
  peak_multiplier?: number;
}

export interface PublicModelCacheGroup {
  group_name: string;
  models: PublicModelCacheItem[];
}

export const PUBLIC_MODELS_TTL = 5 * 60 * 1000;
const CACHE_KEY = "public-models-cache-v1";

interface CachePayload {
  saved_at: number;
  groups: PublicModelCacheGroup[];
}

let inFlight: Promise<PublicModelCacheGroup[]> | null = null;

function readPayload(): CachePayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const payload = JSON.parse(raw) as CachePayload;
    return Array.isArray(payload?.groups) ? payload : null;
  } catch {
    return null;
  }
}

export function readCachedPublicModels(): PublicModelCacheGroup[] | null {
  return readPayload()?.groups || null;
}

export function readCachedPublicModelsAge(): number | null {
  const payload = readPayload();
  return payload ? Date.now() - payload.saved_at : null;
}

function cachePublicModels(groups: PublicModelCacheGroup[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(CACHE_KEY, JSON.stringify({ saved_at: Date.now(), groups }));
}

export async function prefetchPublicModels(force = false): Promise<PublicModelCacheGroup[]> {
  if (inFlight) return inFlight;
  if (!force) {
    const cached = readCachedPublicModels();
    const age = readCachedPublicModelsAge();
    if (cached?.length && age !== null && age < PUBLIC_MODELS_TTL) return cached;
  }

  inFlight = fetch("https://api.vemixapp.com/public/models", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error("Model data unavailable");
      return response.json() as Promise<PublicModelCacheGroup[]>;
    })
    .then((groups) => {
      if (Array.isArray(groups)) cachePublicModels(groups);
      return groups;
    })
    .finally(() => {
      inFlight = null;
    });

  return inFlight;
}

export function startPublicModelsRefresh(): void {
  const cached = readCachedPublicModels();
  if (!cached) return;
  void prefetchPublicModels(true).catch(() => undefined);
}
