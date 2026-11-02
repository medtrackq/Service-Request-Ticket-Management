# BUC Customer Service — Frontend

React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS 4 single-page app with two parts:

| Area | Routes | Notes |
| --- | --- | --- |
| Customer portal (mobile-first, LINE in-app browser) | `/`, `/request/:slug`, `/request/:slug/success`, `/track`, `/track/:ticketNumber#t=<token>`, `/privacy` | Loaded eagerly (~93 KB gzip JS) |
| Staff / admin portal | `/admin/*` | Lazy-loaded chunk; charts (Recharts) in a separate chunk |

## Commands

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api -> http://localhost:8000 (override with VITE_API_PROXY)
npm run build      # tsc -b && vite build -> dist/
npm run typecheck
node e2e/portal-mobile.e2e.mjs   # Playwright E2E (needs dev server + API + admin account)
```

E2E environment variables: `BASE_URL` (default `http://localhost:5173`), `ADMIN_USER` / `ADMIN_PASS`
(default `admin` / `Admin-Pass-2026`, must not require a password change), `SCREEN_DIR` (screenshots,
default `e2e/output`). The test creates real tickets named "โรงพยาบาลทดสอบ E2E" — run it against a
development or staging database only.

## Structure

```
src/
  api/          fetch wrapper (CSRF header, error normalisation, XHR upload progress) + API types
  i18n/         Thai/English provider (tr(), pick()), persisted in localStorage
  lib/          dates (Asia/Bangkok), client-side validation mirroring the backend, file checks/HEIC->JPEG
  components/   UI primitives, icons, toast, FileUploader (camera + gallery, previews, 10-image limit)
  portal/       customer pages
  admin/        staff pages (lazy) — dashboard, tickets, detail, reports, notifications, admin/*
e2e/            Playwright end-to-end script
```

## Security notes

* Staff session = httpOnly cookie set by the API; the CSRF token is kept in memory and sent as
  `X-CSRF-Token` on every non-GET request.
* Tracking tokens are carried in the URL fragment (`#t=`), never in the query string, and sent to the API
  in a POST body.
* Client-side validation is for UX only; the API re-validates every field and file (magic bytes + decode).
