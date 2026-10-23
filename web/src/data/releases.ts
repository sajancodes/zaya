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
}

// Release details come exclusively from verified server metadata.
export const RELEASES_DATA: ReleaseItem[] = [];
