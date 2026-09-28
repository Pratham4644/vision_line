# Database Architecture & MongoDB Schemas

## 1. Persistence Model
File-based JSON configuration has been completely eradicated. MongoDB serves as the single source of truth for:
- Organizations (tenants)
- Sites (physical facilities)
- Users (accounts & credentials)
- Cameras (stream configurations & endpoints)
- Streams (active runtime status & stats)
- Logs (audit trail & security events)

## 2. Collections and Indexes
| Collection | Indexes | Purpose |
|---|---|---|
| `organizations` | `id` (unique) | Multi-tenant isolation |
| `users` | `id` (unique), `email` (unique), `organization_id` | Authentication & profile |
| `sites` | `id` (unique), `organization_id`, `(organization_id, name)` | Multi-facility grouping |
| `cameras` | `id` (unique), `organization_id`, `site_id`, `media_mtx_path` (unique), `status` | Camera registry |
| `streams` | `id` (unique), `camera_id` (unique), `media_mtx_path`, `status` | Live stream metadata |
| `logs` | `id` (unique), `timestamp` (desc), `level`, `category`, `event`, `camera_id`, `site_id`, `user_id`, `organization_id` | Audit & analytics |

## 3. Log Retention
Logs are capped using automated retention policies (default: 30 days, configurable via `LOG_RETENTION_DAYS`). Automated cleanup triggers on application startup and periodically runs without impacting live stream throughput.
