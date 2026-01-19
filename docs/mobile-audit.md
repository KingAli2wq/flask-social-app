# Mobile UI Audit (Phase 0)

Scope: inventory current server-rendered UI (templates + shared components + JS) before any responsive refactors.

> Last updated: **January 19, 2026**

## UI Entry Points

### Templates
Location: `app/ui/templates/`

Templates found:
- `base.html` (global shell)
- `community_guidelines.html`
- `home.html`
- `login.html`
- `privacy.html`
- `register.html`
- `profile.html`
- `public_profile.html`
- `friends_search.html`
- `messages.html`
- `notifications.html`
- `media.html`
- `settings.html`
- `moderation.html`

### Static assets
Location: `app/ui/static/`

Assets found:
- `app/ui/static/js/app.v2.js` (primary UI behaviors)
- `app/ui/static/css/app.css`
- `app/ui/static/img/social-sphere-logo.png`
- `app/ui/static/img/favicon.ico`
- `app/ui/static/default-avatar.png`

### UI routing / page controllers
Location: `app/ui/pages/` (FastAPI routes rendering templates)

Pages found:
- `auth.py` (login/register)
- `home.py`
- `profile.py` (private profile + public profile)
- `friends.py` (friend search)
- `messages.py`
- `notifications.py`
- `media.py`
- `settings.py`
- `moderation.py`
- `policy.py` (privacy + community guidelines)

Router: `app/ui/router.py`

## Localization / i18n

The server injects locale + string tables into the UI via helpers under `app/ui/i18n/` and `app/ui/template_helpers.py`.

## Shared Layout / Component Patterns

### Base layout
Template: `app/ui/templates/base.html`

Key shared UI:
- Global Tailwind via CDN (`tailwindcss.com`) with plugins forms/typography/aspect-ratio
- Inline CSS defining shared primitives:
  - `.input-field` (shared inputs)
  - `.toggle-input` (switch)
  - `.card-surface` (card container appearance)
  - `.mobile-tap-target` (min tap sizing applied in small-screen CSS)
  - `.scrollbar-thin` (custom scrollbar)
- Global overlays/modals:
  - `#app-lock-overlay` (password lock)
  - `#terms-overlay` (terms & conditions modal)
  - `#social-ai-overlay` (Social AI full-screen overlay + mode dropdown)
- Script globals:
  - `window.__LOCALE__`, `window.__I18N__`, `window.__I18N_DEFAULT__`
  - `window.__SOCIAL_CONFIG__` (terms)
- Script include: `/assets/js/app.v2.js` (deferred)
- Inline JS:
  - mobile nav fallback toggler (`#mobile-nav-toggle` / `#mobile-nav-panel`)
  - app lock behavior (locks background via `body[data-app-locked]`)

### Navbar (shared component)
Component: `app/ui/components/layout.py` → `navbar()`

Desktop:
- `<nav>` with links (Feed/Profile/Search/Messages/Notifications/Settings/Media/Moderation)

Mobile:
- Hamburger toggle: `#mobile-nav-toggle`
- Collapsible panel: `#mobile-nav-panel`
- Includes role-gated links via `data-role-gate` / `data-requires-role`

### Template components (server-rendered)
Location: `app/ui/components/`

- `layout.py` (navbar)
- `forms.py` (text/password/textarea/file input helpers)
- `buttons.py` (primary/ghost buttons)
- `cards.py` (post/notification/message card builders)
- `feedback.py` (toast container + spinners; used by templates)

## JavaScript Inventory (event listeners / behaviors)

### Primary JS bundle
File: `app/ui/static/js/app.v2.js`

Exports `window.UI.*` init functions used by pages:
- `initFeedPage()`
- `initLoginPage()`
- `initRegisterPage()`
- `initProfilePage()`
- `initPublicProfilePage({ username })`
- `initMessagesPage()`
- `initFriendSearchPage()`
- `initNotificationsPage()`
- `initMediaPage()`
- `initSettingsPage()`
- `initModerationPage()`

Notable cross-cutting utilities already present in JS:
- `lockBodyScroll()` / `unlockBodyScroll()` (used by moderation panel; useful for other mobile overlays)

### Inline / per-template scripts
- `base.html`: mobile nav fallback toggle + app-lock logic
- `profile.html`: patches `document.getElementById("profile-media")` alias → `avatar-file` (compat shim) + calls `window.UI.initProfilePage()`
- Most pages: call their corresponding `window.UI.init*Page()` inside `DOMContentLoaded`

## Per-page Component Inventory

### Feed / Home
Template: `app/ui/templates/home.html`
Init: `window.UI.initFeedPage()`

Major components:
- Stories rail: `#story-rail`, `#story-rail-items`, `#story-create-button`, `#story-self-pill`
- Story modals: `#story-modal` (create), `#story-viewer` (view)
- Composer:
  - contenteditable editor `#caption-editor` + hidden textarea `#caption`
  - file upload via `components.forms.file_input("file")`
  - preview `#media-preview`, `#media-preview-image`, `#media-preview-video`
  - submit `#post-submit`
- Feed:
  - hashtag filter input `#feed-hashtag-input`, buttons `#feed-hashtag-submit`, `#feed-hashtag-clear`
  - list container `#feed-list`, load more `#feed-load-more`, states `#feed-loading`, `#feed-empty`
- Right-side rail (desktop): trending tags `#trends`, media drafts `#media-drafts`, inline mini AI chat (`#ai-chat-*`)

### Login
Template: `app/ui/templates/login.html`
Init: `window.UI.initLoginPage()`

Major components:
- Form `#login-form`
- Submit `#login-submit`
- Error `#login-error`

### Register
Template: `app/ui/templates/register.html`
Init: `window.UI.initRegisterPage()`

Major components:
- Form `#register-form`
- Submit `#register-submit`
- Error `#register-error`

### Profile (private)
Template: `app/ui/templates/profile.html`
Init: `window.UI.initProfilePage()`

Major components:
- Avatar block:
  - img `#profile-avatar` (also `data-current-user-avatar`)
  - file input `#avatar-file` (hidden)
  - trigger `#profile-upload-trigger`
- Profile display fields: `#profile-display-name`, `#profile-username`, `#profile-location`, `#profile-bio`, `#profile-website`
- Stats: `#profile-post-count`, `#profile-created`, `#profile-followers-count`, `#profile-following-count`
- Edit form `#profile-form` + save button `#profile-save` + feedback `#profile-feedback`
- Recent posts: `#profile-feed`, `#profile-feed-loading`, `#profile-feed-empty`

### Public profile
Template: `app/ui/templates/public_profile.html`
Init: `window.UI.initPublicProfilePage({ username })`

Major components:
- Header: `#public-profile-avatar`, `#public-profile-username`, `#public-profile-bio`, `#public-profile-location`, `#public-profile-website`
- Follow button: `#public-profile-follow-button`
- Posts: `#public-profile-posts`, `#public-profile-posts-loading`, `#public-profile-posts-empty`, `#public-profile-post-count`

### Friends search
Template: `app/ui/templates/friends_search.html`
Init: `window.UI.initFriendSearchPage()`

Major components:
- Search form `#friend-search-form`
- Input `#friend-search-input`
- Results `#friend-search-results`
- Feedback `#friend-search-feedback`

### Messages
Template: `app/ui/templates/messages.html`
Init: `window.UI.initMessagesPage()`

Major components:
- Sidebar:
  - friend list `#friend-list`, count `#friend-count`
  - group list `#group-list`, count `#group-count`
  - request lists `#incoming-requests`, `#outgoing-requests` with count `#incoming-count`
  - group create trigger `#group-create-trigger`
  - Social AI open button `data-social-ai-open="true"`
- Thread pane:
  - header `#chat-header`, lock indicator `#lock-indicator`
  - message list `#message-thread`
  - form `#message-form`, send button `#message-send`
  - attachments: input `#message-attachment-input`, trigger `#message-attachment-trigger`, preview `#message-attachment-preview`
  - reply UI: `#message-reply-banner`, cancel `#message-reply-cancel`
- Modals:
  - create group `#group-create-modal` (+ `data-group-create-close`)
  - invite group `#group-invite-modal` (+ `data-group-invite-close`)

### Notifications
Template: `app/ui/templates/notifications.html`
Init: `window.UI.initNotificationsPage()`

Major components:
- Mark all read button `#notifications-mark`
- List `#notifications-list`
- Loading `#notifications-loading`
- Empty `#notifications-empty`
- Count badge `#notifications-count`

### Media
Template: `app/ui/templates/media.html`
Init: `window.UI.initMediaPage()`

Major components:
- Upload form `#media-upload-form`
- File input `#media-file`
- Preview `#media-preview`, `#media-preview-img`, `#media-preview-video`
- Feedback `#media-upload-feedback`
- History list `#media-upload-history`
- Reel container `#media-reel` (scroll-snap), loader `#media-reel-loader`, empty `#media-reel-empty`
- Fullscreen toggle `#media-fullscreen-toggle`

### Settings
Template: `app/ui/templates/settings.html`
Init: `window.UI.initSettingsPage()`

Major components:
- Avatar: img `#settings-avatar` (also `data-current-user-avatar`), file `#settings-avatar-file`, trigger `#settings-avatar-trigger`
- Logout: `#settings-logout`
- Profile basics: form `#settings-profile-form`, save `#settings-profile-save`
- Contact/security:
  - email input `#settings-email-input`
  - verify buttons `#settings-verify-email`, `#settings-resend-email`
  - verify panel `#settings-verify-panel`, code `#settings-verify-code`, submit `#settings-verify-submit`
  - password form `#settings-password-form` + save `#settings-password-save`
- Preferences:
  - language select `#settings-language`
  - toggles `#settings-pref-email-dm`, `#settings-pref-friend-requests`, `#settings-pref-follower-dms`
- Danger zone: `#settings-export-data`, `#settings-deactivate`

### Moderation
Template: `app/ui/templates/moderation.html`
Init: `window.UI.initModerationPage()`

Major components:
- Dashboard cards: `[data-moderation-card]` + stats `[data-moderation-stat]`
- Tables:
  - users table `#moderation-user-table` / body `#moderation-user-body`
  - posts table `#moderation-post-table` / body `#moderation-post-body`
- Overlays:
  - dataset panel `#moderation-dataset-panel` (contains `#moderation-panel-search`, `#moderation-panel-table`)
  - detail modal `#moderation-detail-modal`
  - confirm modal `#moderation-confirm-modal`

## Notes (mobile risk hotspots to revisit in later phases)
- Multiple overlays exist (terms, social-ai, story modal/viewer, group modals, moderation overlays). They need consistent body-scroll locking + focus management.
- Several pages use 2-column layouts at `lg:` (home/profile/settings) and a fixed sidebar width in messages (`md:grid-cols-[320px,1fr]`). These will need mobile-first stacking.
- Tables on moderation page use `overflow-x-auto` already, but need an explicit mobile strategy (card rows or scroll affordance).
