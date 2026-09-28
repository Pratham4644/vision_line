# Structured Logging System

## 1. Schema
Every log entry adheres to a structured JSON schema persisted to the MongoDB `logs` collection:
- `id`: Unique UUID
- `timestamp`: ISO-8601 UTC timestamp
- `level`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `category`: `AUTH`, `CAMERA`, `STREAM`, `SITE`, `USER`, `API`, `DATABASE`, `SYSTEM`, `SECURITY`, `ADMIN`
- `event`: Enumerated event code (e.g. `LOGIN_SUCCESS`, `STREAM_STARTED`, `CAMERA_DISCONNECTED`)
- `message`: Human-readable summary
- `request_id`: Request correlation ID from `X-Request-ID` header
- `user_id`: Acting user UUID (if authenticated)
- `organization_id`: Tenant UUID
- `site_id`: Facility UUID (if correlated)
- `camera_id`: Camera UUID (if correlated)
- `stream_id`: Stream UUID (if correlated)
- `metadata`: Sanitized contextual key-value payload

## 2. Redaction and Data Protection
The logging system actively filters out sensitive information:
- Passwords (`password`, `pass`, `pwd`) are masked as `***`.
- Bearer tokens (`token`, `jwt`, `authorization`) are masked as `***`.
- RTSP URLs containing inline basic authentication (`rtsp://admin:pass@host:554/path`) are sanitized to `rtsp://***:***@host:554/path`.
