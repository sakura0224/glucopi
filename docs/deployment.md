# Deployment Notes

## Backend

### Runtime Dependencies

- Python
- MySQL
- MongoDB
- environment variables defined in `backend/.env.example`

### Local Startup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Important Backend Requirements

- valid WeChat app credentials
- valid database connection strings
- valid JWT secret
- valid LLM API key and base URL
- prediction checkpoint directories present under `backend/algorithm/GluPred/checkpoint/`

## Frontend

### Local Startup

```bash
cd frontend/miniprogram
npm install
```

Then:

1. update `frontend/miniprogram/utils/api-config.js`
2. import the project into WeChat DevTools
3. rebuild Mini Program dependencies if DevTools requires `miniprogram_npm`

## Notes

- `project.private.config.json` is intentionally excluded
- local `.env` files are intentionally excluded
- model checkpoint files are included in the repository, which makes the repository heavier than a code-only project
