# API Overview

## Base Path

The backend mounts its HTTP API under:

```text
/api/v1
```

## Route Groups

Based on the backend router, the main API groups are:

- `/auth`: login, registration, account checks, WeChat login
- `/user`: user information and profile-related operations
- `/doctors`: doctor-facing information queries
- `/bindings`: doctor-patient binding relationships
- `/glucose`: glucose records, summaries, and trend queries
- `/insulin`: insulin-related records
- `/diet`: diet-related records
- `/record`: combined record workflows
- `/chat`: chat history, read state, and summaries
- `/prediction`: short-term glucose prediction
- `/ws`: WebSocket endpoints for chat

## Frontend Integration Notes

The Mini Program currently uses:

- `utils/request.js` for HTTP calls
- `utils/socket.js` for WebSocket connections
- `utils/api-config.js` for endpoint configuration

Before local or remote deployment, update the HTTP and WebSocket hosts in `frontend/miniprogram/utils/api-config.js`.

## Existing Source Material

The original workspace included an API usage note. Its ideas have been folded into this repository structure, but the repository now uses the cleaned frontend request wrapper and backend route organization found in the current codebase.
