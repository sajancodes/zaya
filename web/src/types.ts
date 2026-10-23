export interface ReleaseInfo {
  version: string;
  platform: string;
  filename: string;
  url: string;
  sha256: string;
  size: number;
  release_notes: string;
  published_at: number;
}

export interface AnalyticsMetrics {
  downloads: {
    total: number;
    windows: number;
    android: number;
  };
  installations: {
    total: number;
    windows: number;
    android: number;
  };
  active: {
      online_now?: number;
    last_24h: number;
    last_7d: number;
    last_30d: number;
  };
  version_distribution: Record<string, number>;
  daily_installs: Array<{ day: string; count: number }>;
  daily_downloads: Array<{ day: string; count: number }>;
  daily_installs_since?: number;
  retention?: {mode: string; last_completed: number | null; limitation: string};
  update_health?: Array<{day:string; platform:string; target_version:string | null; available?:number; download_verified?:number; installer_started?:number; failed?:number}>;
  update_health_definition?: string;
  updated_at: number;
}

export interface DocArticle {
  id: string;
  title: string;
  category: string;
  description: string;
  content: string; // Markdown or rich HTML
}
