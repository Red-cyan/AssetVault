export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export type Asset = {
  id: string;
  name: string;
  stem: string;
  extension: string;
  asset_type: string;
  path: string;
  size_bytes: number;
  file_hash: string | null;
  thumbnail_path: string | null;
  thumbnail_url: string | null;
  description: string | null;
  author: string | null;
  rating: number;
  is_favorite: boolean;
  is_deleted: boolean;
  deleted_at: string | null;
  exists_on_disk: boolean;
  missing_since: string | null;
  last_opened_at: string | null;
  file_modified_at: string | null;
};

export type AssetDetail = Asset & {
  tags: Array<{ id: string; name: string; color: string | null; source: string }>;
};

export type AssetList = {
  items: Asset[];
  total: number;
  page: number;
  page_size: number;
};

export type AssetFolderGroup = {
  name: string;
  path: string;
  total_count: number;
  primary_count: number;
  support_count: number;
  size_bytes: number;
};

export type Folder = {
  id: string;
  name: string;
  path: string;
  is_active: boolean;
  last_scanned_at: string | null;
};

export type Tag = {
  id: string;
  name: string;
  color: string | null;
  source: string;
  created_at: string;
};

export type Task = {
  id: string;
  type: string;
  status: "pending" | "running" | "success" | "failed" | "canceled";
  progress: number;
  total: number;
  processed: number;
  message: string | null;
  error: string | null;
  payload: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type AssetCleanupResult = {
  excluded_removed: number;
  missing_removed: number;
};

export type AssetBatchUpdateResult = {
  matched_count: number;
  updated_count: number;
  tagged_count: number;
  trashed_count: number;
};

export type StatsOverview = {
  total_assets: number;
  total_size_bytes: number;
  favorite_count: number;
  tag_count: number;
  folder_count: number;
  recent_assets_7d: number;
  type_stats: Array<{
    asset_type: string;
    count: number;
    size_bytes: number;
  }>;
  top_extensions: Array<{
    extension: string;
    count: number;
  }>;
};

export type Project = {
  id: string;
  name: string;
  description: string | null;
  cover_asset_id: string | null;
  asset_count: number;
  created_at: string;
  updated_at: string;
};

export type ProjectDetail = Project & {
  assets: Array<{
    role: string;
    created_at: string;
    asset: Asset;
  }>;
};

export type AppSettings = {
  cache_dir: string;
  theme: string;
  ai_base_url: string;
  ai_api_key_configured: boolean;
  ai_chat_model: string;
  thumbnail_quality: number;
};

export type EmbeddingIndexStatus = {
  indexed_assets: number;
  total_assets: number;
  model: string;
  dimensions: number;
};

export type UserProfile = {
  id: string;
  username: string;
  email: string | null;
  display_name: string | null;
  is_active: boolean;
  created_at: string;
};

export type RuntimeInfo = {
  auth_mode: "local" | "password";
  authentication_required: boolean;
};

let runtimeInfoPromise: Promise<RuntimeInfo> | null = null;

export type AiConnectionTestResult = {
  configured: boolean;
  message: string;
};

export type DatabaseBackupResult = {
  path: string;
  size_bytes: number;
  created_at: string;
};

export type AiAnalyzeResult = {
  asset: AssetDetail;
  tags: string[];
  description: string;
  source: "openai-compatible" | "local-heuristic";
  model: string | null;
  elapsed_ms: number;
};

export type NaturalLanguageSearchResult = {
  items: Asset[];
  total: number;
  query: string;
  interpreted_keywords: string[];
  mode: string;
};

export type DuplicateAssetGroup = {
  file_hash: string;
  size_bytes: number;
  count: number;
  items: Asset[];
};

export type DuplicateAssetResponse = {
  groups: DuplicateAssetGroup[];
  total_groups: number;
  total_assets: number;
  hashed_assets: number;
};

export type TrashSummary = {
  deleted_count: number;
  purged_count: number;
};

export type MissingAssetScanResult = {
  checked_count: number;
  missing_count: number;
  restored_count: number;
};

export function getToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("assetvault_token");
}

export function setToken(token: string) {
  window.localStorage.setItem("assetvault_token", token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("assetvault_token");
}

export function getRuntimeInfo(): Promise<RuntimeInfo> {
  if (!runtimeInfoPromise) {
    runtimeInfoPromise = fetch(`${API_BASE}/runtime`)
      .then(async (response) => {
        if (!response.ok) throw new Error((await response.text()) || response.statusText);
        return response.json() as Promise<RuntimeInfo>;
      })
      .catch((error) => {
        runtimeInfoPromise = null;
        throw error;
      });
  }
  return runtimeInfoPromise;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (response.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("assetvault:unauthorized"));
    }
  }
  if (!response.ok) {
    const text = await response.text();
    try {
      const payload = JSON.parse(text) as { detail?: string };
      throw new Error(payload.detail || text || response.statusText);
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(text || response.statusText);
      throw error;
    }
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
