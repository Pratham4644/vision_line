// ── Roles & Status ──────────────────────────────────────────────────────────

export type UserRole = 'SUPER_ADMIN' | 'ORG_ADMIN' | 'OPERATOR' | 'VIEWER';
export type CameraStatus = 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'UNKNOWN';
export type SourceProtocol = 'RTSP';
export type IngestMode = 'EDGE' | 'DIRECT';

// ── User ────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  organization_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ── Camera ──────────────────────────────────────────────────────────────────
// Matches backend CameraResponse schema

export interface Camera {
  id: string;
  organization_id: string;
  site_id: string;
  name: string;
  description: string | null;
  source_protocol: SourceProtocol;
  ingest_mode: IngestMode;
  media_path: string;
  enabled: boolean;
  configured_resolution: string | null;
  configured_fps: number | null;
  status: CameraStatus;
  has_credentials: boolean;
  created_at: string;
  updated_at: string;
}

// Matches backend CameraDetailResponse schema (extends CameraResponse)
export interface CameraDetail extends Camera {
  whep_url: string | null;
  rtsp_playback_url: string | null;
  measured_fps: number | null;
  measured_bitrate: string | null;
}

// Matches backend CameraPlaybackResponse schema
export interface CameraPlayback {
  camera_id: string;
  organization_id: string;
  media_path: string;
  whep_url: string;
  rtsp_url: string;
  reader_credentials: { username: string; password: string };
  ice_servers: Array<{ urls: string[] }>;
  control_state: string;
  media_state: string;
  ingest_state: string;
}

// ── Site ────────────────────────────────────────────────────────────────────
// Matches backend SiteResponse schema

export interface Site {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  location: string | null;
  created_at: string;
  updated_at: string;
}

// ── Organization ────────────────────────────────────────────────────────────

export interface Organization {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

// ── Health ───────────────────────────────────────────────────────────────────

export interface DetailedHealth {
  status: string;
  database: boolean;
  timestamp: string;
}

// ── Audit Log ───────────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  organization_id: string | null;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  timestamp: string;
  request_id: string | null;
  details: Record<string, any>;
}

// ── API Wrapper ─────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  request_id?: string;
}
