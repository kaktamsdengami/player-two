# PLAYER TWO dashboard (T15)

React + Vite. Projector-friendly dark UI with tabs: Live (agent view, action timeline, voice
indicator + intent buttons), Bugs & fixes (bug cards, clip, Fix?/Merge buttons, Devin panel with
PR link and upstream comparison), Debrief (heatmap, notes, product placement), Plans, Parent.

```bash
cd web && npm install
npm run dev                                   # mock data from ../docs/api-mock.json (labelled MOCK DATA)
VITE_API_BASE=http://localhost:8000 npm run dev   # live API (T14): REST /api/*, SSE /api/events, /media/*
npm run build && npm run lint
```

Buttons post `VoiceIntent` (`source: "button"`) to `POST /api/intent`; `stop` also calls `POST /api/stop`.
In mock mode nothing is posted and the mock SSE events replay in a loop.
