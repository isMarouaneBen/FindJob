# FindJob frontend

React 18 + Vite + Tailwind + React Query + React Router + Axios.

## Stack

- **Vite** dev server / bundler
- **React 18** with React Router v6
- **TailwindCSS** for styling (`src/index.css` has small component classes:
  `.btn-primary`, `.field-input`, `.card`, etc.)
- **@tanstack/react-query** for server state (the recommendations query
  prefers the structured profile, falling back to the CV).
- **Axios** in `src/api/client.js`. Base URL via `VITE_API_URL`.
- **@react-oauth/google** for Google Sign-In. The button hides itself if
  `VITE_GOOGLE_CLIENT_ID` is empty.

## Setup

```bash
cd platform/frontend
cp .env.example .env       # then edit if needed
npm install
npm run dev                # http://localhost:5173
```

The dev server proxies nothing — the FastAPI backend must be running and
allow CORS from `http://localhost:5173` (already enabled with `*` in
`platform/app/main.py`).

## Auth model (prototype)

Authentication is **client-side only** for now:

- `signUp` / `signIn` store the user in `localStorage` (plain text password
  — prototype only). See `src/auth/localUsers.js`.
- Google Sign-In decodes the credential JWT in the browser and stores the
  resulting `{ email, name, picture }`.
- Sessions live in `sessionStorage` so they vanish when the tab closes.

To replace with a real backend later: swap the bodies of `signIn`, `signUp`
and `signInWithGoogle` in `src/auth/AuthContext.jsx` with calls to your
`/auth/*` endpoints and store the returned JWT.

## Flow

1. `/register` or `/login` — local credentials or Google.
2. `/onboarding/cv` — drag-and-drop upload to `POST /cv/upload`. The
   returned `cv_id` is cached in `localStorage` under `findjob.cvId`.
3. `/onboarding/profile` — optional structured form mirroring the
   backend `ProfileForm` schema. Saved under `findjob.profile`.
4. `/recommendations` — calls
   `POST /recommendations` (form) if the profile was filled, otherwise
   `POST /recommendations/from-cv/{cv_id}`. Cards show the score with a
   per-signal breakdown (vector / tech overlap / seniority / contract /
   location / remote / language) plus matched and missing technologies.

## File layout

```
src/
├── api/                # axios + endpoint wrappers
├── auth/               # AuthContext + localStorage user store
├── routes/             # ProtectedRoute
├── components/         # Layout, Header, OfferCard, FileDropzone
├── pages/              # Login, Register, OnboardingCV/Profile, Recommendations
├── lib/cn.js           # clsx wrapper
├── App.jsx             # provider stack + routes
└── main.jsx
```

## Getting a Google Client ID

1. https://console.cloud.google.com/apis/credentials
2. **Create credentials → OAuth client ID → Web application**
3. Authorised JavaScript origins: `http://localhost:5173`
4. Paste the client ID into `.env` as `VITE_GOOGLE_CLIENT_ID`. No backend
   work needed — the token is decoded client-side.
