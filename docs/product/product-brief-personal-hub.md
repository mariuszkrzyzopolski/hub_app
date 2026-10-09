# Product Brief: Personal Hub — Gift List & Event Roles

**Version:** 2.4
**Date:** 2026-05-17
**Type:** Personal Internal Tool
**Stack:** Python 3.12 · Django 6.0.5 · uv · pyproject.toml · PostgreSQL 16 · Makefile

---

## 1. Vision & Purpose

A lightweight, self-hosted personal hub website that acts as an organiser for social occasions. The owner manages gift lists and event role sheets; guests visit via a shared link, enter a password, and coordinate using a session-scoped name — no accounts, no tracking, no friction.

The hub is architected as a **catalogue**: `core/` is the connective tissue linking independent mini-apps, each potentially on different specs or purposes. The homepage is the catalogue directory. Future projects plug in as new catalogue entries. Gift lists and events are the first two mini-apps; others can follow without restructuring the foundation.

The hub solves a real coordination problem: social platform threads bury polls and lists under conversation noise. The hub is a single point of information, claims, and responsibilities — the owner shares the link, reminds guests manually, and the hub holds the state.

---

## 2. Target Users

| Role | Description |
|---|---|
| **Owner / Admin** | The website owner. Technical user. Manages all content via Django's built-in admin panel. Single superuser — multi-admin is permanently out of scope. |
| **Guests** | Friends, family, or colleagues. Access lists/events via a shared link and password. Identified by a unique session-scoped name — no accounts required. |

---

## 3. Core Features

### 3.1 Guest Identity & Session Model

- On first visit (at any page), guests are prompted to enter a name before accessing any content.
- Names are **globally unique** across the system — enforced at DB level and with a real-time uniqueness hint in the input.
- If a chosen name is already taken, `core/names_recommendation.py` suggests alternatives (e.g. *"Piotr_K", "Piotr2"*) via a simple string factory.
- Minimum name length: **3 characters**.
- The name is stored in the Django session and travels automatically across all lists and events — the name prompt fires **once per session**, ever.
- The session also stores `authenticated_slugs` — a list of all slugs the guest has unlocked. Authenticating multiple lists/events accumulates in a single session list.
- Name is **strictly session-scoped** — no persistence between sessions. Guests are responsible for remembering their chosen name.
- Name is displayed read-only in the **header** on every page.
- Name can only be **changed via the header** — available on every page.
- Changing name triggers an **"Update Claims"** action, available per list/event page — updates all assignments carrying the old name within that list/event.

### 3.2 Gift List (`/gifts/<slug>`)

A shared gift registry page for a specific occasion (e.g. birthday, Christmas).

**Behaviour:**
- Admin creates a list with a name, optional description, event date, and a set of gift items.
- Each list has its own access password (4–20 characters).
- The list page is **not served at all** until the guest has passed the password gate and entered a name. Only the password form renders for unauthenticated visitors — no titles, item counts, or any list data appear in the response.
- After passing the gate, the slug is added to `authenticated_slugs` in the session. All gated pages are served with `Cache-Control: no-store` — applied via `@method_decorator(never_cache, name='dispatch')` on `PasswordGatedViewMixin`, covering **both** the gate form responses and authenticated content responses.
- After mutating the `authenticated_slugs` list in the session, `request.session.modified = True` must be set explicitly — Django does not detect in-place list mutations automatically.
- Guests see all gift items with their current claim status and claimant name (or an empty field).
- A guest claims a gift by pressing a single **"Assign"** button — their session name is assigned automatically. One person per gift (exclusive).
- **Edit** and **Delete** controls appear next to every claimed entry. Delete requires a **confirmation dialog**. All actions are logged to the audit log.
- Claimed gifts are visually distinguished (e.g. strikethrough or badge).
- Race condition on simultaneous claim uses `select_for_update(nowait=True)` — the lock attempt fails immediately (rather than blocking) and returns a plain dialog: *"Ten prezent został właśnie zajęty. Odśwież stronę i wybierz inny."* ("This gift was just claimed. Refresh and choose another.")
- If the list has zero visible items, guests see a *"listing creation in progress, please return later"* page.
- If the list is inactive/archived, guests see a custom *"this listing is currently archived and will return soon"* page. Claims survive deactivation.

**Admin controls (Django admin):**
- Full CRUD for lists and items with inline editing.
- Set or rotate the per-list password — rotation increments `password_version` using a DB-level atomic `F('password_version') + 1` update, immediately invalidating all existing guest sessions for that slug.
- `event_date` field — drives auto-archive and index display.
- `is_active` toggle — soft archive, data preserved.
- Manual **"Archive"** button per list.
- Auto-archive fires automatically **14 days after `event_date`** — always anchors to the current value; updating the date resets the countdown. Implemented via cron + `manage.py archive_expired`.
- View and restore any assignment via the audit log.
- Share info panel — copyable plain-text stats (X/Y claimed, last activity, unique claimants).

---

### 3.3 Event Roles (`/events/<slug>`)

A role-assignment board for a specific event (e.g. house party, picnic, road trip).

**Behaviour:**
- Admin creates an event with a name, description, event date, and a structured set of **categories** (e.g. *Food*, *Entertainment*). Each category contains one or more **roles**. Categories with zero roles are not rendered.
- Each event has its own access password (4–20 characters).
- The event page is **not served** until the guest has passed the password gate and entered a name.
- Guests see the full role board grouped by category, with claimant names visible next to every role.
- A guest assigns a role by pressing a single **"Assign"** button — their session name is used automatically.
- **Category-level assignment** — a guest can assign themselves to an entire category. This atomically fills every unassigned role within that category with their name (`via_category=True`). Already-claimed roles are left untouched. The operation uses `select_for_update()` with `order_by('id')` (consistent lock ordering to prevent deadlocks) within an atomic transaction.
- **Category locking** — when a category is claimed, all individual roles within it are **locked**. No one can edit or claim individual roles while the category is claimed. To modify individual roles, the category claim must first be explicitly released via an **"Unclaim Category"** action.
- **Edit** and **Delete** controls appear next to every role assignment. Delete requires a confirmation dialog. All actions are logged.
- Race condition handling identical to gift lists.
- If the event has zero visible categories/roles, guests see the *"creation in progress"* page.
- Inactive/archived events show the custom archived page. Assignments survive.

**Admin controls (Django admin):**
- Full CRUD for events, categories, and roles with inline editing.
- Set or rotate password — increments `password_version` via `F('password_version') + 1` (atomic DB update), invalidating all sessions for that slug.
- `event_date`, `is_active`, manual archive button, auto-archive (14 days).
- View and restore any assignment via audit log.
- Share info panel — copyable stats (X/Y roles filled, last activity, unique assignees).

---

### 3.4 Admin Panel (`/admin/`)

Django's built-in admin, extended to cover all management requirements.

**Capabilities:**
- Full CRUD with inline editing for all models.
- Password field (stored hashed; validated 4–20 chars on save; set in plain text, hashed on save). `save_model()` compares submitted value against stored hash via `check_password()` before re-hashing — avoids double-hashing on non-password saves.
- `is_active` toggle and manual archive button per list/event.
- Auto-archive management command (`manage.py archive_expired`) called by cron.
- **Audit log** — read-only log of all claim/assignment/deletion events, plus 3× consecutive failed authentication attempts on a single slug. Each log entry includes action type, assignee name, session ID, timestamp, and deletion/restoration state.
- **Restore button** on each deleted audit log entry — one-click restoration of the exact previous state. Implemented via `get_urls()` override on `ModelAdmin` with a callable `list_display` column rendering an anchor to the restore endpoint.
- **Usage statistics dashboard** — per list/event: completion %, unique claimant names, date of last activity.
- Customised list views — search, filter by active/inactive/archived, ordering by date.

**Access model:** Single superuser. Credentials via `createsuperuser`. Admin session fully separate from guest sessions. Multi-admin is out of scope.

---

## 4. Access & Security Model

| Area | Protection |
|---|---|
| `/` (hub homepage) | Public — catalogue directory |
| `/gifts/` (index) | Public — active gift lists by name + progress |
| `/events/` (index) | Public — active events by name + progress |
| `/gifts/<slug>/` | Password gate + name gate; no page source visible before auth; session-based |
| `/events/<slug>/` | Password gate + name gate; no page source visible before auth; session-based |
| `/admin/` | Django superuser login |
| Guest identity | Session-scoped unique name — no accounts |

**Password gate implementation:**
- `core/mixins.py` — `PasswordGatedViewMixin` handles: session slug tracking, password version checking, `Cache-Control: no-store`, and name gate enforcement.
- The mixin overrides `dispatch()` (not `get()`) so POST requests to claim/edit/delete endpoints are also blocked for unauthenticated guests. The mixin must appear **leftmost** in the class inheritance chain: `class MyView(PasswordGatedViewMixin, BaseView)`.
- `Cache-Control: no-store` applied via `@method_decorator(never_cache, name='dispatch')` at the class level — covers both gate form responses and authenticated content responses uniformly.
- If session lacks the slug or the stored `password_version` doesn't match the model's current version, only the password form renders — no titles, counts, or data.
- On correct password submission, slug and current `password_version` are stored in session.
- Incorrect password shows a generic error — no hint about correct value.
- Three consecutive failures on a single slug are written to the audit log.
- Passwords stored hashed using Django's `make_password` / `check_password`.
- Threat model: **outsiders** — household/shared-device access is acceptable. CSRF protection is a nice-to-have, not a hard requirement.

---

## 5. Information Architecture

```
/                                   → Hub homepage (catalogue — active lists & events)
/gifts/                             → Public index of active gift lists
/gifts/<slug>/                      → Gift list (gated)
/gifts/<slug>/claim/                → POST: claim a gift item
/gifts/<slug>/edit/<id>/            → POST: edit a claim
/gifts/<slug>/delete/<id>/          → POST: delete a claim
/gifts/<slug>/update-claims/        → POST: rename assignee across list

/events/                            → Public index of active events
/events/<slug>/                     → Event role board (gated)
/events/<slug>/assign/              → POST: assign a single role
/events/<slug>/assign-category/     → POST: atomically assign all unassigned roles in a category
/events/<slug>/unclaim-category/    → POST: release a category claim
/events/<slug>/edit/<id>/           → POST: edit a role assignment
/events/<slug>/delete/<id>/         → POST: delete a role assignment
/events/<slug>/update-claims/       → POST: rename assignee across event

/admin/                             → Django built-in admin (superuser only)
```

---

## 6. Data Model

### core app (abstract base models)
- **PasswordGatedModel** *(abstract)*: `slug` (unique), `name` (max 200 chars), `description`, `password_hash`, `password_version` (int), `is_active`, `is_archived`, `event_date`, `created_at`
- **AuditLogEntry** *(abstract)*: `action`, `assignee_name`, `session_id`, `timestamp`, `is_deleted`, `restored_at`
- **GuestName**: `name` (unique, 3–200 chars) — global unique name registry

### gifts app
- **GiftList** *(extends PasswordGatedModel)*
- **GiftItem**: `list` (FK→GiftList, CASCADE), `name` (max 200 chars), `description`, `order`
- **GiftClaim**: `item` (OneToOne→GiftItem, CASCADE), `assignee_name`, `session_id`, `claimed_at`, `updated_at`
- **GiftAuditLog** *(extends AuditLogEntry)*: `list` (FK→GiftList), `item` (FK→GiftItem, nullable), snapshot fields for restore

### events app
- **Event** *(extends PasswordGatedModel)*
- **RoleCategory**: `event` (FK→Event, CASCADE), `name` (max 200 chars), `order`
- **Role**: `category` (FK→RoleCategory, CASCADE), `name` (max 200 chars), `description`, `order`
- **RoleAssignment**: `role` (OneToOne→Role, CASCADE), `assignee_name`, `session_id`, `via_category` (bool), `assigned_at`, `updated_at`
- **EventAuditLog** *(extends AuditLogEntry)*: `event` (FK→Event), `role` (FK→Role, nullable), snapshot fields for restore

**Key model rules:**
- All `on_delete=CASCADE` down the ownership chain — deleting a parent silently removes children and claims.
- `password_version` increments on every password rotation via `F('password_version') + 1` (atomic DB update) — guests with stale versions must re-authenticate.
- `GuestName` creation must be wrapped in `transaction.atomic()` as a savepoint; the view catches `IntegrityError` gracefully (DB unique constraint is the final defence against the race window between Python-level check and DB write).
- Categories with zero roles excluded from public querysets.
- `is_archived` is set by manual admin action or auto-archive — separate from `is_active` (admin visibility toggle).
- Slugs auto-generated using `python-slugify` (not Django's built-in `slugify`) to correctly transliterate non-ASCII/Polish characters — prevents empty or colliding slugs from names like *"Urodziny Kaśki"*.

---

## 7. Tech Stack & Project Structure

| Concern | Choice |
|---|---|
| Language | Python 3.12 (minimum; pinned in `pyproject.toml`) |
| Web framework | Django 6.0.5 |
| Dependency management | `uv` + `pyproject.toml`; `uv.lock` committed for reproducible builds |
| Database | PostgreSQL 16 (minimum PostgreSQL 14; required by Django 6.0) |
| Production server | Gunicorn (`gunicorn hub.wsgi:application --workers 3 --bind 0.0.0.0:8000`) |
| Frontend | Django templates + vanilla CSS; inline vanilla JS only for: confirmation dialogs, race condition dialogs, name collision hints, auto-refresh (v2). No framework, no build step. Standard Django template inheritance (`extends`/`block`/`include`) throughout — no template partials. |
| Guest auth | Session-based; `PasswordGatedViewMixin` in `core/mixins.py` |
| Admin | Django built-in `/admin/`, customised via `ModelAdmin` classes |
| Scheduler | cron + `manage.py archive_expired` |
| Setup & ops | Makefile + bash scripts — no Docker; `make install` (uv sync), `make dev` (start Gunicorn + PostgreSQL), `make migrate`, `make createsuperuser`; `scripts/wait-for-db.sh` polls PostgreSQL before running migrations |
| Slug generation | `python-slugify` — handles non-ASCII/Polish characters correctly |
| Language | Polish throughout — all user-facing copy written directly in Polish in templates; no i18n system, no translation files |

**Project layout:**
```
pyproject.toml
Makefile
scripts/
  wait-for-db.sh
hub/                        ← Django project (settings, urls, wsgi)
core/                       ← Shared catalogue layer
  models.py                 ← PasswordGatedModel, AuditLogEntry (abstract), GuestName
  mixins.py                 ← PasswordGatedViewMixin
  session.py                ← get/set guest name, authenticated_slugs helpers
  names_recommendation.py   ← name collision suggestion factory
  decorators.py             ← (legacy shim if needed)
  templates/core/
    base.html
    password_gate.html
    name_gate.html
    archived.html
    in_progress.html
  static/
    style.css
management/
  commands/
    archive_expired.py
gifts/                      ← Gift list mini-app
  models.py
  views.py
  urls.py
  admin.py
  templates/gifts/
events/                     ← Event roles mini-app
  models.py
  views.py
  urls.py
  admin.py
  templates/events/
templates/                  ← Project-level templates (homepage)
manage.py
```

---

## 8. UX Principles

- **Catalogue-first** — the homepage is the portal. Every mini-app is one entry in the catalogue.
- **Clarity first** — guests understand the state of a list in under 5 seconds.
- **Zero friction** — no sign-up, no email, no CAPTCHA. Share a link, share a password, enter a name, done.
- **Hard password and name wall** — nothing about the list renders before both gates are passed.
- **Trust-based editing** — anyone can edit or delete any entry. Admin is the backstop via audit log and restore.
- **Simple and direct** — all user-facing copy is short, plain, and informational. No decoration, no personality, no filler. Every message tells the guest exactly what happened or what to do next. Written directly in Polish in templates — never hardcoded in English, never in translation files.
- **Mobile-friendly** — primary use case is guests on their phone in a group chat.
- **Calm design** — clean, readable, minimal colour palette. Functional, not decorative.

---

## 9. Milestone Map

| Milestone | Focus | Scope |
|---|---|---|
| **v1 — Functional Core** | System works end-to-end, securely, reliably | Session auth + `PasswordGatedViewMixin` (overrides `dispatch()`, leftmost in MRO, `@method_decorator(never_cache)` applied uniformly); unique guest names at DB level + `IntegrityError` savepoint handling; mandatory name gate; `core/` shared interface (abstract models, mixins, session.py, names_recommendation.py); `session.modified = True` set after `authenticated_slugs` mutation; PostgreSQL 16 + Makefile + bash scripts (with `wait-for-db.sh`) + Gunicorn; `python-slugify` for slug generation; gift lists end-to-end (claim via `select_for_update(nowait=True)`, edit, delete, confirmation dialogs); event roles end-to-end (assign, category locking via `select_for_update()` with `order_by('id')`, atomic transactions, unclaim category); race condition handling with Fibonacci backoff dialog; `Cache-Control: no-store`; `event_date` on all models; auto-archive at 14 days via cron + management command; "archived" and "creation in progress" pages; `on_delete=CASCADE` chains; 200-char field limits; 4–20 char password policy; 3-char min name; progress indicators on homepage `(X/Y claimed)`; read-only audit log in admin; full Django admin CRUD with inline editing; password `save_model()` with hash-detection before re-hashing; `password_version` incremented via `F()` expression; all user-facing copy written directly in Polish in templates |
| **v2 — Operational Polish** | Owner runs live events confidently | Audit log restore button (via `get_urls()` override + callable `list_display` anchor); name collision suggestion factory live; password rotation → session invalidation via `password_version`; share info panel (copyable stats per list/event); auto-refresh via `setInterval` JSON-count poll (not `<meta refresh>` — avoids resetting open dialogs); basic usage statistics dashboard in admin (completion %, unique names, last activity); admin list view improvements (search, filter, ordering) |
| **v3 — Guest Experience** | Guests can complete tasks without friction | Clean frontend templates — full visual design pass using standard Django template inheritance; mobile optimisation — thumb-friendly layout and spacing; all copy reviewed for clarity and brevity in Polish; homepage catalogue MVP — gift lists and events as distinct visual sections |
| **v4 — Admin UX** | Owner management comfort | Custom admin screens within Django admin constraints; task-oriented shortcuts; mobile-friendlier admin flows |
| **v5 — Optional Extensions** | Data & insights | Contribution heatmap (which guests claimed most — owner-facing, optional); statistics extensions; potential new mini-apps plugging into `core/` catalogue |

---

## 10. Out of Scope

- Real-time updates (WebSockets / Django Channels) — auto-refresh in v2 is sufficient
- User accounts or login system
- Email notifications
- Multi-admin support — single superuser permanently
- Public sharing without password
- Read-only guest mode — name entry is mandatory for all visitors
- Comments or messaging on items
- Mobile native app
- Attendee hint dropdowns — replaced by session-name model
- English UI for guests — site is Polish-only; no language switching planned
- Django i18n system — no `.po`/`.mo` files, no `{% trans %}`, no `compilemessages`; Polish copy written directly in templates

---

## 11. Implementation Notes

**PostgreSQL 16 from v1:** Enables reliable row-level locking for atomic category assignment (`select_for_update()`). SQLite write-locking is insufficient for the concurrent group-chat-burst scenario this app is designed for. Django 6.0 requires PostgreSQL 14 minimum; project pins PostgreSQL 16. `make dev` is a single command that starts Gunicorn and PostgreSQL via bash scripts; `scripts/wait-for-db.sh` polls the DB socket before running migrations.

**Session vs. cookies:** The session is the single auth mechanism — no per-slug cookies. The session stores: guest name, `authenticated_slugs` list, and per-slug `password_version` at time of authentication. One clock governs everything. Session age: Django default 2 weeks (`SESSION_COOKIE_AGE = 1209600`). Session security settings in `settings.py`: `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, `SESSION_COOKIE_SECURE = True` when serving over HTTPS.

**Session mutation:** After any in-place mutation of a session list (e.g. `authenticated_slugs.append(slug)`), `request.session.modified = True` must be set explicitly. Django's session framework only detects top-level assignment, not in-place mutations. Alternatively, reassign: `request.session['authenticated_slugs'] = [*existing, slug]`.

**Password rotation invalidation:** `password_version` (int) increments on every rotation using `F('password_version') + 1` — a single atomic DB `UPDATE`, not a read-modify-write. `PasswordGatedViewMixin` compares session-stored version against current model version — mismatch forces re-authentication. No manual session invalidation required.

**Atomic category assignment:** `select_for_update()` with `order_by('id')` on all roles in the category within a single `transaction.atomic()` block. The consistent lock order (by `id`) prevents deadlocks if two concurrent category assignments are attempted. Use `select_for_update(of=('self',))` if the queryset uses `select_related()` to avoid locking parent rows unnecessarily.

**Gift claim concurrency:** Single-gift claim uses `select_for_update(nowait=True)` — raises `DatabaseError` immediately if the row is already locked, enabling fast-fail to the Fibonacci backoff dialog rather than blocking the request.

**Name uniqueness race condition:** Three-layer defence: (1) Python-level `GuestName.objects.filter(name=name).exists()` check for real-time UI hint; (2) DB `unique=True` constraint on `GuestName.name` as final guard; (3) view wraps `GuestName.objects.create()` in `transaction.atomic()` as a savepoint and catches `IntegrityError` gracefully — returns name-taken response with suggestions rather than a 500.

**Category locking:** When any role in a category carries `via_category=True`, all roles in that category are locked for individual edit/claim. The category header shows "covered by [name]." Releasing the category claim (`unclaim-category`) clears `via_category` flags and unlocks individual roles.

**Auto-archive:** `manage.py archive_expired` queries all `GiftList` and `Event` records where `is_archived=False` and `event_date < (today - 14 days)`, sets `is_archived=True`. Cron runs this daily. Updating `event_date` resets eligibility automatically — no extra logic needed.

**Slug generation:** Uses `python-slugify` (not Django's built-in `slugify`) in the `save()` override. Django's `slugify` strips non-ASCII characters, producing empty or colliding slugs for Polish names. `python-slugify` transliterates correctly: *"Urodziny Kaśki"* → `"urodziny-kaski"`. Admin uses `prepopulated_fields = {'slug': ('name',)}` for live preview.

**Password hashing:** `save_model()` compares the submitted password field value against the stored hash via `check_password()` before deciding whether to re-hash. If the submitted value matches (i.e. the admin saved without changing the password), the hash is left unchanged.

**Django template approach:** Standard Django template inheritance (`extends`/`block`/`include`) is used throughout — no Django 6.0 template partials syntax. All user-facing copy is written directly in Polish in templates: dialogs, status messages, gate pages, archived/in-progress pages. No i18n system, no `{% trans %}`, no `.po`/`.mo` files, no `LOCALE_PATHS`, no `compilemessages` build step. The Django admin interface remains in English as a superuser tool — this is acceptable.

**Inline JS rule:** Vanilla JS inline in templates is permitted strictly for: confirmation dialogs, race condition dialogs, name collision hints, auto-refresh. No framework. No build step. Nothing else without explicit approval.

---

## 12. Success Criteria

- A guest goes from shared link → completed assignment in under 60 seconds
- Admin sets up a new gift list or event in under 5 minutes via Django admin
- No list/event source or data is exposed before a valid password and name are entered
- Password rotation immediately prevents re-entry without re-authentication
- No data lost on server restart (PostgreSQL persistence)
- Works correctly on mobile browsers
- `make up` brings the full stack in a single command
- Admin can restore any accidentally deleted claim in two clicks

---

*Brief v2.4 — removed Docker entirely; setup now via Makefile + bash scripts; `scripts/wait-for-db.sh` replaces Docker Compose health check. Ready for implementation.*
