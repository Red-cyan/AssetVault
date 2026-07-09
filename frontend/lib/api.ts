export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export type Asset = {
  id: string;
  name: string;
  stem: string;
  extension: string;
  asset_type: string;
  path: string;
  size_bytes: number;
  thumbnail_path: string | null;
  thumbnail_url: string | null;
  description: string | null;
  author: string | null;
  rating: number;
  is_favorite: boolean;
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
  created_at: string;
};

export type AssetCleanupResult = {
  excluded_removed: number;
  missing_removed: number;
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
  ai_embedding_model: string;
  thumbnail_quality: number;
};

export type AiConnectionTestResult = {
  configured: boolean;
  message: string;
};

export function getToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("assetvault_token");
}

export function setToken(token: string) {
  window.localStorage.setItem("assetvault_token", token);
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
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
