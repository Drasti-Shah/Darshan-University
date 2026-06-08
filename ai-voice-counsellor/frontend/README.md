# Darshan Voice Counsellor — Frontend (Next.js)

Admin console for the AI voice admission counsellor. Talks to the Flask backend
(`../app.py`).

## Pages
| Route | What it does |
|---|---|
| `/login` | Demo login (admin / darshan123) |
| `/dashboard` | Live stats + recent calls + backend status |
| `/dial` | Place a single outbound counselling call |
| `/leads` | Searchable table of captured students + CSV export |
| `/campaign` | Bulk-dial a list of numbers |
| `/analytics` | Charts: leads by qualification, top programs |
| `/call-logs` | All calls + click-to-view Gujarati transcript |

## Stack
Next.js 14 (App Router) · React 18 · Tailwind CSS · Recharts. Auth is a simple
frontend-only demo (localStorage) — swap for NextAuth/JWT in production.

## Run

1. **Start the backend** (in the parent folder):
   ```powershell
   cd ..
   python app.py        # http://localhost:5000
   ```
2. **Start the frontend:**
   ```powershell
   npm install
   npm run dev          # http://localhost:3000
   ```
3. Open http://localhost:3000 and log in with **admin / darshan123**.

## Config
`.env.local`:
```
NEXT_PUBLIC_API_BASE=http://localhost:5000   # Flask backend URL
NEXT_PUBLIC_DEMO_USER=admin
NEXT_PUBLIC_DEMO_PASS=darshan123
```
The backend already sends permissive CORS headers, so the browser can call it
directly. For production, point `NEXT_PUBLIC_API_BASE` at your deployed API and
lock down CORS.
