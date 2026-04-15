# SonaSurfer

SonaSurfer is a full-stack app that turns natural language music requests into curated Spotify playlists.
It combines a React frontend, a FastAPI backend, Spotify OAuth, and LLM-assisted song extraction and validation.

## Why this project is interesting

- End-to-end product workflow from auth to playlist creation
- Real integration with Spotify APIs (OAuth, playlist creation, track search/add)
- Streaming chat UX that progressively builds playlists
- LLM-assisted extraction with guardrails and structured parsing

## Tech stack

- Frontend: React (Create React App), Tailwind CSS, Testing Library
- Backend: FastAPI, Spotipy, Anthropic SDK, httpx, BeautifulSoup
- Auth/Integrations: Spotify OAuth + REST APIs

## Repository structure

- `frontend/` React client UI and interaction flow
- `backend/` FastAPI API, service layer, and integrations

## Local setup

### 1) Backend

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r backend/requirements.txt`
3. Create `backend/.env` with required variables:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REDIRECT_URI`
   - `ANTHROPIC_API_KEY`
   - `BRAVE_API_KEY` (optional but recommended for web validation)
4. Start backend:
   - `uvicorn main:app --reload --app-dir backend`

### 2) Frontend

1. Install dependencies:
   - `cd frontend && npm install`
2. Start frontend:
   - `npm start`

Frontend runs at `http://localhost:3000`; backend defaults to `http://localhost:8000`.

## Testing

- Backend unit tests:
  - `cd backend && pytest -q`
- Frontend tests:
  - `cd frontend && npm test -- --watchAll=false`

## Security and privacy notes

- Credentials are loaded from environment variables; `.env` files are gitignored.
- OAuth state checking is used for CSRF protection in the Spotify login flow.
- Debug mode defaults to off in checked-in config.

## Current limitations / next improvements

- Add richer backend test coverage for API endpoints and streaming flow
- Add integration tests for Spotify interactions with mocks
- Improve frontend component test coverage for loading/progress UX
