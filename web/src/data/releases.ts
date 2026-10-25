export interface ReleaseDownload {
  format: string;
  label: string;
  filename: string;
  downloadUrl: string;
  sha256: string;
  sizeFormatted: string;
  commands: string[];
  note: string;
}

export interface ReleaseItem {
  version: string;
  tag: string;
  channel: 'Stable' | 'Beta' | 'Preview';
  platform: 'windows' | 'android' | 'linux' | 'cross-platform';
  platformName: string;
  date: string;
  filename: string;
  downloadUrl: string;
  sha256: string;
  sizeBytes: number;
  sizeFormatted: string;
  highlights: string[];
  fullChangelog: string[];
  knownIssues?: string[];
  requirements: string[];
  unsigned?: boolean;
  downloads?: ReleaseDownload[];
}

// Stable releases use verified server metadata; experimental betas use published artifact metadata.
export const RELEASES_DATA: ReleaseItem[] = [];
