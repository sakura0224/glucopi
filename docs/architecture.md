# Architecture

## System Shape

GlucoPI uses a frontend/backend split:

- `frontend/miniprogram/`: WeChat Mini Program client
- `backend/`: FastAPI service and prediction-related assets

## Frontend

The Mini Program is organized around three main tabs:

- Home
- Message
- My

Additional subpackages cover:

- login and login-code flows
- profile editing
- chat
- record entry
- glucose trend visualization
- doctor binding and follow-up
- glucose prediction

The frontend communicates with the backend through:

- HTTP requests for business APIs
- WebSocket for chat

## Backend

The backend exposes its APIs under `/api/v1` and is composed of:

- auth
- user
- doctors
- bindings
- glucose
- insulin
- diet
- record
- chat
- prediction
- websocket chat

Core technical components:

- FastAPI for HTTP and WebSocket endpoints
- SQLAlchemy + MySQL for relational user/profile/binding data
- Motor + MongoDB for chat and time-series style health records
- PyTorch-based prediction workflow for short-term glucose forecasting

## Data and Prediction Flow

1. The Mini Program collects user-entered health data.
2. The backend stores structured account/profile data in MySQL.
3. Record and chat-oriented data are handled through MongoDB collections.
4. The prediction service loads pretrained patient profile metadata and checkpoint assets.
5. The service prepares recent user glucose-related sequences and returns a short-term prediction result.

## Supporting Assets

- UI screenshots: [screenshots](./screenshots)
- frontend structure diagram: [frontend-structure.svg](./diagrams/frontend-structure.svg)
