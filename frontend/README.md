# Frontend

React + Vite single-page app for the Strategy Lab (Defensive Black-Litterman
model and Growth model). See the root [README](../README.md) for what the models
do and how they were tested.

```bash
npm install
npm run dev      # local dev server
npm run build    # production build into dist/
```

The API base URL defaults to the deployed backend and can be overridden with
`VITE_API_URL` (see `env.example`). The app pings the backend on page load so
that a sleeping free-tier instance starts waking up immediately.
