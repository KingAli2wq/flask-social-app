# SocialSphere Backend + UI Architecture

> Last updated: **January 19, 2026**

This repository is a **FastAPI** backend that serves:

- JSON APIs (under multiple routers in `app/routers/`)
- A server-rendered web UI (templates + shared components in `app/ui/`)

## High-Level Layout

### Runtime entry points
- `run_server.py` starts Uvicorn with `app.main:app`.
- `app/main.py` wires middleware, routers, and static mounts.

### Core packages
- `app/routers/`: API route definitions (feature boundaries)
- `app/services/`: domain logic (email, AI, safety, moderation helpers, etc.)
- `app/models/` + `app/db/models.py`: persistence models and helpers
- `app/database.py`: engine/session lifecycle + init
- `app/middleware/`: cross-cutting request policies (app lock, terms enforcement)
- `app/ui/`: server-rendered UI (templates, components, page controllers, JS/CSS)

## Request Lifecycle (Typical)

1. **Client request** hits `app/main.py`.
2. **Middleware** runs first:
   - `AppLockMiddleware` can block the UI/API while locked.
   - `TermsAcceptanceMiddleware` can block authenticated requests until the latest terms are accepted.
3. **Router** handles the route (`app/routers/*.py`).
4. **Service layer** performs domain logic (`app/services/*`).
5. **DB session** is used via `app/database.py` helpers / `SessionLocal`.
6. **Response** returns JSON or a rendered HTML template (UI routes).

## API Surface (Routers)

Routers are included in `app/main.py` and generally map to one feature area per file:

- Authentication: `auth.py`
- Profiles: `profiles.py`
- Posts: `posts.py`
- Stories: `stories.py`
- Uploads + media: `uploads.py`, `media.py`
- Messaging: `messages.py` (DMs + group chats)
- Notifications: `notifications.py`
- Friends + follows: `friends.py`, `follows.py`
- Moderation: `moderation.py`
- Realtime: `realtime.py`
- Settings: `settings.py`
- AI features: `ai.py`, `ai_posts.py`, `chatbot.py`
- System utilities: `system.py`, `spellcheck.py`, `mailgun_webhooks.py`

## Database + Migrations

Schema changes are tracked with Alembic in `alembic/versions/`.

Recent milestone migrations include:
- 2026-01: user bans; group chat member roles
- 2025-12: support tickets; language preference; AI chat session status
- 2025-12: AI chatbot tables; group chat security
- 2024-12: roles, follows, friendships, engagement tables, dislikes, email verification, replies

Operationally:
- Apply migrations with `alembic upgrade head` (or the repo scripts, if preferred).

## Server-Rendered UI (`app/ui/`)

The UI is rendered by FastAPI routes in `app/ui/pages/` and uses:

- Templates: `app/ui/templates/`
- Shared template components: `app/ui/components/` (layout/forms/buttons/cards/feedback)
- Static assets: `app/ui/static/` (`js/app.v2.js`, `css/app.css`, images)

This pattern keeps UI concerns isolated while still sharing auth/session state and policies with the JSON APIs.

## Adding a New Feature (Suggested Pattern)

1. Add/extend a router file in `app/routers/`.
2. Put reusable logic in `app/services/`.
3. Add/modify DB models as needed and generate an Alembic migration.
4. If UI is needed:
   - Create or extend a template in `app/ui/templates/`.
   - Add page-specific logic in `app/ui/static/js/app.v2.js` (or a new JS module if you decide to split).
5. Add/extend tests under `tests/`.

## Legacy Notes

An earlier version of this document described a desktop component UI architecture (Tkinter-style components). If that is still relevant to another companion project, keep it there; the current repository UI is server-rendered (templates + JS), as described above.
- Check that component is registered
- Verify data has stable IDs
- Look for manual `destroy()` calls outside components

## Conclusion

This component-based architecture brings DevEcho up to par with professional social media applications. Users will experience:

✅ **Zero flicker** when receiving notifications
✅ **Smooth scrolling** in all feeds
✅ **Instant reactions** to user actions
✅ **Professional polish** matching industry standards

The architecture is scalable, maintainable, and ready for future enhancements.
