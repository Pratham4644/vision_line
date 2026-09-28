# Authentication & Role-Based Access Control (RBAC)

## 1. Overview
Authentication uses industry-standard JSON Web Tokens (JWT) signed with HMAC-SHA256 (`HS256`). Passwords are securely hashed with `bcrypt` (work factor 12) via `passlib`.

## 2. Roles Hierarchy
1. **SUPER_ADMIN**: Full system-wide access across all organizations and tenants.
2. **ADMIN**: Full management access within their assigned organization (users, cameras, sites, streams, logs, settings).
3. **OPERATOR**: Live stream monitoring, camera toggle (enable/disable), and stream control (start/stop/restart), logs view.
4. **VIEWER**: Read-only live stream viewing and camera list inspection. No access to administrative settings or destructive actions.

## 3. Permission Matrix
| Permission | SUPER_ADMIN | ADMIN | OPERATOR | VIEWER |
|---|:---:|:---:|:---:|:---:|
| `camera:read` | Yes | Yes | Yes | Yes |
| `camera:create` | Yes | Yes | No | No |
| `camera:update` | Yes | Yes | Yes | No |
| `camera:delete` | Yes | Yes | No | No |
| `stream:read` | Yes | Yes | Yes | Yes |
| `stream:start` | Yes | Yes | Yes | No |
| `stream:stop` | Yes | Yes | Yes | No |
| `site:read` | Yes | Yes | Yes | Yes |
| `site:create/update/delete`| Yes | Yes | No | No |
| `user:read/create/update/delete`| Yes | Yes | No | No |
| `logs:read` | Yes | Yes | Yes | No |
| `system:read` | Yes | Yes | Yes | Yes |
