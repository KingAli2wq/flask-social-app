# Terms Enforcement Integration Notes

## Database & Migration
- Alembic revision `20241124_add_terms_acceptance_fields.py` adds two nullable columns on `users`:
  - `accepted_terms_version` (VARCHAR 32)
  - `terms_accepted_at` (TIMESTAMP with timezone)
- Run `alembic upgrade head` (or `python run_server.py --migrate`) after pulling to ensure the schema is up to date.

## Backend Contracts
- Canonical contract lives in `TERMS_AND_CONDITIONS.md`. It is exposed publicly at `GET /terms` for the UI download link.
- Constant `CURRENT_TERMS_VERSION = "1.0.0"` resides in `app/constants.py`. Bump this when the markdown changes and re-run migrations if needed.
- New endpoint `POST /auth/accept-terms` accepts `{"version": "1.0.0"}` and updates the authenticated user.
- `TermsAcceptanceMiddleware` blocks every authenticated request (401+ routes) until the stored version matches `CURRENT_TERMS_VERSION`. Exemptions: `/auth/login`, `/auth/register`, `/auth/accept-terms`, `/auth/me`, `/health`, `/api`, `/docs`, `/redoc`, `/openapi`, and static mounts.

## Frontend Behaviour
- `base.html` now renders a full-screen modal overlay (`#terms-overlay`) that is controlled entirely by `app/ui/static/js/app.v2.js`.
- The JS bundle bootstraps `window.__SOCIAL_CONFIG__` values (version string, message, `/terms` download URL) and stores acceptance state in `localStorage` (`socialsphere:terms-version`).
- Any API call receiving HTTP 451 triggers the modal, fetches the markdown body, and blocks interaction until the user accepts.
- Acceptance submits to `/auth/accept-terms`, stores the version locally, closes the modal, and forces a soft reload so the last action can be retried.

## Operational Notes
1. **Updating the contract:** edit `TERMS_AND_CONDITIONS.md` and bump `CURRENT_TERMS_VERSION`. Communicate the effective date in the document header before deployment.
2. **Deploy order:** apply the Alembic migration, deploy backend (so middleware + endpoint exist), then deploy the UI bundle. The middleware gracefully handles clients that have not upgraded yet by returning 451.
3. **Testing:**
   - Create a fresh user, log in, and confirm the modal appears immediately on first authenticated call.
   - Hit `POST /auth/accept-terms` manually (curl or Swagger) to ensure the version updates.
   - Verify `/terms` serves the markdown file.
4. **Support:** If the contract fails to load, the modal instructs users to download `/terms`. Declining signs the user out, so support should remind users to re-accept after reviewing.

These steps keep both backend enforcement and frontend messaging in sync whenever the contract content changes.
