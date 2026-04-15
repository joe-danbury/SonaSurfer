# SonaSurfer Frontend

This is the React client for SonaSurfer. It handles Spotify login, chat interactions, and live playlist-building UI while the backend validates and adds tracks.

## Scripts

- `npm start` - runs the app locally on `http://localhost:3000`
- `npm test` - runs frontend tests
- `npm run build` - creates a production build

## Local development

1. Install dependencies with `npm install`
2. Start the app with `npm start`
3. Ensure backend is running (default API target is `http://localhost:8000`)

## Testing

Run tests once (non-watch mode):

- `npm test -- --watchAll=false`

## Notes

- Authentication is performed via Spotify OAuth through the backend.
- The UI is optimized for progressive feedback while tracks are validated and added.
