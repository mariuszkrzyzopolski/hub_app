---
title: "Product Brief Distillate: Personal Hub"
type: llm-distillate
source: "product-brief-personal-hub.md"
version: 2.4
created: "2026-05-10"
updated: "2026-05-17"
purpose: "Token-efficient context for downstream PRD/implementation planning"
---

# Personal Hub — Implementation Distillate

## PRODUCT IDENTITY
- Self-hosted personal coordination tool; owner shares links manually in group chats
- Solves: social thread noise buries polls/lists; hub = single source of truth for claims/responsibilities
- Architecture: `core/` = catalogue connecting independent mini-apps; homepage = catalogue directory
- v1 ships two mini-apps: gift lists + event roles; others plug in later without restructuring core
- Owner = single technical superuser; guests = friends/family, anonymous beyond session-scoped name
- Threat model: outsiders only; household/shared-device access acceptable; no CSRF hard requirement

---

## AUTH & SESSION MODEL
- **Single mechanism:** Django session only — no per-slug cookies, no two-clock problem
- Session stores: `guest_name` (str), `authenticated_slugs` (list of str), `{slug}_password_version` (int per slug)
- **Session settings:** `SESSION_COOKIE_AGE = 1209600` (2 weeks default — accepted); `SESSION_COOKIE_HTTPONLY = True`; `SESSION_COOKIE_SAMESITE = 'Lax'`; `SESSION_COOKIE_SECURE = True` when serving over HTTPS
- **Session mutation rule:** after any in-place mutation of `authenticated_slugs`, set `request.session.modified = True` explicitly — Django does not detect list `.append()` automatically
- **Password gate:** `PasswordGatedViewMixin` in `core/mixins.py` — overrides `dispatch()` (not `get()`) so POST endpoints are also blocked; must appear **leftmost** in class MRO: `class MyView(PasswordGatedViewMixin, BaseView)`; checks slug in `authenticated_slugs` AND stored version matches model's `password_version`; mismatch → re-auth required
- `Cache-Control: no-store` applied via `@method_decorator(never_cache, name='dispatch')` — covers **all** responses (gate form + authenticated content) uniformly
- On successful auth: slug + current `password_version` written to session
- On failed auth: generic error only, no hints; 3× consecutive failures on same slug → audit log entry
- **Password rotation:** `password_version` incremented via `F('password_version') + 1` (atomic DB `UPDATE`) → all existing sessions for that slug immediately fail version check → forced re-auth; no manual session flush needed
- Password policy: 4–20 chars, validated at Django admin save, stored hashed via `make_password`/`check_password`; `save_model()` uses `check_password()` to detect unchanged passwords before re-hashing

---

## GUEST NAME / IDENTITY
- Names globally unique — enforced at **both** DB level (unique constraint on `GuestName.name`) and application level
- Application-level check required too — DB-only has race condition window if two guests submit same name simultaneously
- Min 3 chars, max 200 chars
- Name entered once per session; prompt fires once ever — travels across all lists/events automatically
- Name gate fires after password gate — guest cannot see any list/event content without both passing
- If guest deep-links directly (bypassing homepage), name gate fires at gated page — no gap
- **Name collision:** `core/names_recommendation.py` — pure string factory, no session dependency, suggests alternatives (e.g. "Piotr_K", "Piotr2") shown as real-time hint in input
- **Name change:** via header only (available every page); triggers per-list/event "Update Claims" button (not automatic) — scopes update to `session_id` match, not name match, to avoid colliding with other sessions using same name
- Unique name = de-facto cross-device identity: same name on two devices correctly updates all claims
- Name is session-scoped only — expires with session, no persistence, no "welcome back" recognition — intentional
- Header: displays current name read-only on all pages
- Homepage: purely catalogue directory — no name management responsibility

---

## GIFT LIST MECHANICS
- Claim = single "Assign" button; session name assigned automatically — no per-item text entry
- One claim per item (OneToOne); race condition uses `select_for_update(nowait=True)` — fails fast (raises `DatabaseError` immediately if row locked) → plain dialog: *"Ten prezent został właśnie zajęty. Odśwież stronę i wybierz inny."*
- Edit + Delete on every claim; Delete requires confirmation dialog
- All claim/edit/delete actions written to `GiftAuditLog`
- Zero items visible → "listing creation in progress, please return later" page
- Archived list → "this listing is currently archived and will return soon" page; claims survive
- Progress shown on homepage index: "(3/6 claimed)" next to list name

---

## EVENT ROLES MECHANICS
- Structure: Event → RoleCategory → Role → RoleAssignment
- Categories with zero roles: excluded from public querysets entirely — not rendered
- Single role assign: "Assign" button → session name written to `RoleAssignment`
- **Category-level assign:** atomically fills all unassigned roles in category with session name; `via_category=True` on each written assignment; uses `select_for_update(order_by('id'))` within `transaction.atomic()` — consistent lock ordering prevents deadlocks; mandatory for concurrent safety
- **Category lock:** when any role in category has `via_category=True`, ALL roles in that category locked — no individual edit/claim possible while lock active
- **Unclaim category:** explicit action clears `via_category=True` on all assignments in category → unlocks individual roles; POST `/events/<slug>/unclaim-category/`
- Category header shows "covered by [name]" when category is locked
- Race condition handling identical to gift lists
- Zero visible categories/roles → "creation in progress" page
- Archived event → custom archived page; assignments survive
- Progress on homepage: "(5/8 roles filled)"

---

## DATA MODEL SUMMARY

### core (abstract — inherited by all mini-apps)
```
PasswordGatedModel (abstract):
  slug            unique, auto-generated from name via python-slugify (non-ASCII safe), editable
  name            max 200 chars
  description     text, optional
  password_hash   hashed via make_password
  password_version int, incremented via F('password_version') + 1 (atomic DB UPDATE)
  is_active       bool — admin visibility toggle (soft hide, data preserved)
  is_archived     bool — set by manual action or auto-archive (separate from is_active)
  event_date      date — drives auto-archive countdown + index display
  created_at      datetime

AuditLogEntry (abstract):
  action          str (claim/edit/delete/auth_fail)
  assignee_name   str
  session_id      str
  timestamp       datetime
  is_deleted      bool
  restored_at     datetime nullable

GuestName:
  name            unique, 3–200 chars — global registry
                  creation wrapped in transaction.atomic() savepoint; IntegrityError caught gracefully
```

### gifts
```
GiftList(PasswordGatedModel)
GiftItem: list FK(CASCADE), name max200, description, order
GiftClaim: item OneToOne(CASCADE), assignee_name, session_id, claimed_at, updated_at
GiftAuditLog(AuditLogEntry): list FK, item FK nullable, snapshot fields for restore
```

### events
```
Event(PasswordGatedModel)
RoleCategory: event FK(CASCADE), name max200, order
Role: category FK(CASCADE), name max200, description, order
RoleAssignment: role OneToOne(CASCADE), assignee_name, session_id, via_category bool, assigned_at, updated_at
EventAuditLog(AuditLogEntry): event FK, role FK nullable, snapshot fields for restore
```

**All on_delete=CASCADE** down ownership chain — parent deletion silently removes children and claims; intentional, acceptable for this use case.

---

## ADMIN CAPABILITIES
- Full CRUD + inline editing for all models
- Slug: auto-generated via `python-slugify` from name; unique constraint — duplicate name triggers clear validation error with rename recommendation
- Password set in plain text → hashed on save; 4–20 char validation at save; `save_model()` uses `check_password()` to detect unchanged passwords before re-hashing (avoids double-hashing)
- `is_active` toggle — hides from public index, does not delete data
- Manual "Archive" button per list/event
- Auto-archive: `manage.py archive_expired` — daily cron; sets `is_archived=True` where `is_archived=False AND event_date < today-14d`; always uses current `event_date` value — date update resets countdown
- **Audit log:** read-only in admin; shows all claim/edit/delete events + 3× consecutive auth failures per slug; each entry has "Restore" button — implemented via `get_urls()` override + callable `list_display` column; one-click restores exact previous state
- **Share info panel:** per list/event — copyable plain-text stats (X/Y claimed, last activity, unique names); owner copies manually into reminder message — no generated text
- **Usage statistics dashboard:** completion %, unique claimant names, last activity date per list/event
- Admin list views: search, filter by active/inactive/archived, order by date
- Single superuser only — `createsuperuser`; multi-admin permanently out of scope

---

## URL STRUCTURE
```
/                                   public catalogue homepage
/gifts/                             public index — active gift lists + progress
/gifts/<slug>/                      gated gift list
/gifts/<slug>/claim/                POST claim
/gifts/<slug>/edit/<id>/            POST edit claim
/gifts/<slug>/delete/<id>/          POST delete claim
/gifts/<slug>/update-claims/        POST rename assignee across list (scoped to session_id)

/events/                            public index — active events + progress
/events/<slug>/                     gated event board
/events/<slug>/assign/              POST assign single role
/events/<slug>/assign-category/     POST atomic category assign
/events/<slug>/unclaim-category/    POST release category claim
/events/<slug>/edit/<id>/           POST edit assignment
/events/<slug>/delete/<id>/         POST delete assignment
/events/<slug>/update-claims/       POST rename assignee across event (scoped to session_id)

/admin/                             Django superuser only
```

---

## CORE MODULE RESPONSIBILITIES
```
core/models.py              PasswordGatedModel, AuditLogEntry (abstract), GuestName
core/mixins.py              PasswordGatedViewMixin — full gate logic, version check, Cache-Control
core/session.py             get_guest_name, set_guest_name, get_authenticated_slugs, authenticate_slug
core/names_recommendation.py  pure string factory — no session dep; generates name alternatives
core/templates/core/
  base.html
  password_gate.html
  name_gate.html
  archived.html             "archived, will return soon" page
  in_progress.html          "creation in progress" page
management/commands/
  archive_expired.py        cron target — daily auto-archive
```

---

## TECH STACK DECISIONS & RATIONALE
- **Django 6.0.5** (pinned, not "latest stable"); Python 3.12 minimum (pinned in `pyproject.toml`)
- **PostgreSQL 16** (minimum PostgreSQL 14 — required by Django 6.0); not SQLite: group-chat-burst requires row-level locking via `select_for_update()`
- **Gunicorn** production server: `gunicorn hub.wsgi:application --workers 3 --bind 0.0.0.0:8000`; Django's `runserver` must not be used in production
- **Makefile + bash scripts — no Docker:** `make install` = `uv sync`; `make dev` = start PostgreSQL + Gunicorn via scripts; `make migrate` = run migrations; `make createsuperuser` = create admin; `scripts/wait-for-db.sh` polls PostgreSQL socket before migrations run; single-command setup mandatory — PostgreSQL requirement raises local setup bar
- **`uv` + `pyproject.toml`:** `uv.lock` committed for reproducible builds; `uv sync --frozen` used in `make install`
- **`python-slugify`:** replaces Django's built-in `slugify`; correctly transliterates non-ASCII/Polish names
- **No JS framework, no build step:** inline vanilla JS in templates permitted only for: confirmation dialogs, race condition dialogs, name collision hints, auto-refresh — nothing else without explicit approval
- **Standard Django template inheritance** (`extends`/`block`/`include`) throughout — no Django 6.0 template partials syntax; keep templates simple and unconditional
- **Polish hardcoded in templates:** all user-facing copy written directly in Polish in templates — no Django i18n system, no `{% trans %}`/`gettext`, no `.po`/`.mo` files, no `LOCALE_PATHS`, no `compilemessages` build step; Django admin remains in English (superuser tool, acceptable)
- **Language policy:** Polish is the sole guest-facing language; no language switching, no English UI for guests — permanently out of scope
- **Cron + management command** for auto-archive — zero extra dependencies, transparent, fits self-hosted ethos; Django 6.0 `django.tasks` not used for this
- **Django session** (not custom cookies) — single auth mechanism, one expiry clock; `SESSION_COOKIE_AGE = 1209600` (2 weeks); `SESSION_COOKIE_HTTPONLY = True`; `SESSION_COOKIE_SAMESITE = 'Lax'`; `SESSION_COOKIE_SECURE = True` over HTTPS

---

## FIELD VALIDATION RULES
| Field | Rule |
|---|---|
| Guest name | 3–200 chars, globally unique, real-time collision hint |
| List/event password | 4–20 chars, validated on admin save |
| GiftItem.name, Role.name, RoleCategory.name, GiftList.name, Event.name | max 200 chars |
| Slug | auto-generated via `python-slugify` from name (non-ASCII safe), editable, unique per model, duplicate blocked with error at admin |

---

## UX BEHAVIOUR RULES
- All destructive actions (delete): confirmation dialog required before execution
- Race condition (claim conflict): Fibonacci backoff dialog — "try again in 1, 2, 3, 5, 8 minutes…"
- Zero content (no items/roles): "creation in progress" page — not a 404
- Archived: custom "archived, will return soon" page — not a 404; data intact
- Name taken: inline suggestion from `names_recommendation.py` — not just rejection
- All copy: short, plain, informational — no decoration, no personality filler; tells the guest exactly what happened or what to do next; written directly in Polish in templates
- No read-only guest mode — name entry mandatory for all visitors; site purpose = coordination not observation

---

## MILESTONE MAP (ABBREVIATED)
| | Milestone | One-line focus |
|---|---|---|
| v1 | Functional Core | Works end-to-end, securely, reliably |
| v2 | Operational Polish | Owner runs live events confidently |
| v3 | Guest Experience | Guests can complete tasks without friction |
| v4 | Admin UX | Owner management comfort |
| v5+ | Optional Extensions | Heatmap, stats, new mini-apps |

**v1 must include:** session auth + `PasswordGatedViewMixin` (overrides `dispatch()`, leftmost MRO, `@method_decorator(never_cache)` on all responses); `session.modified = True` after `authenticated_slugs` mutation; unique names at DB level + `IntegrityError` savepoint handling + name gate; `core/` shared interface; PostgreSQL 16 + Makefile + bash scripts (`scripts/wait-for-db.sh`) + Gunicorn; `python-slugify`; gift lists E2E (`select_for_update(nowait=True)` on claims); event roles E2E (category lock + `select_for_update(order_by('id'))` + unclaim); race condition Fibonacci backoff dialogs; Cache-Control headers; `event_date` + auto-archive; archived/in-progress pages; CASCADE chains; field validation; progress indicators; read-only audit log; Django admin CRUD; password `save_model()` hash detection; `password_version` via `F()` expression; **all user-facing copy in Polish, hardcoded in templates — no i18n system**

**v2 adds:** audit log restore (via `get_urls()` + callable `list_display`); name suggestion factory live; password rotation invalidation; share info panel; auto-refresh via `setInterval` JSON-count poll (not `<meta refresh>`); usage stats dashboard; admin list view improvements

**v3 adds:** clean frontend templates using standard Django template inheritance; mobile optimisation; all copy reviewed for clarity and brevity in Polish; homepage catalogue MVP

**v4 adds:** custom admin screens within Django admin constraints; task-oriented shortcuts; mobile-friendlier admin flows

---

## EXPLICITLY REJECTED / OUT OF SCOPE
- SQLite as primary DB — concurrency risk under group-chat-burst load
- Per-slug cookies — replaced by unified session mechanism
- Per-item free-text name entry — replaced by session name + Assign button
- Attendee hint dropdowns — replaced entirely by session-name model
- Homepage as name management screen — homepage is catalogue only
- Read-only guest mode — all visitors must enter name
- CSRF hard requirement — nice-to-have only; threat model is outsiders, not household
- WebSockets / Django Channels — auto-refresh (v2) is sufficient
- Email notifications — out of scope
- Multi-admin — permanently out of scope, single superuser only
- User accounts / login system — out of scope
- Public sharing without password — out of scope
- Comments / messaging — out of scope
- Mobile native app — out of scope
- Docker / Docker Compose — no containerisation; setup handled via Makefile + bash scripts only
- Generative reminder messages — share info panel provides stats only; owner writes message manually
- AI/ML for name suggestions — pure string factory only
- English UI for guests — Polish-only; permanently out of scope
- Django i18n system — no `.po`/`.mo`, no `{% trans %}`, no `compilemessages`; Polish written directly in templates
- Language switching — permanently out of scope
- Django 6.0 template partials — not used; standard `extends`/`block`/`include` throughout

---

## OPEN RISKS FOR IMPLEMENTATION
1. **`select_for_update(of=('self',))` when using `select_related()`:** if category-assign queryset is ever extended to join related tables, the `of=` parameter must be specified to avoid locking parent rows unnecessarily — increases contention
2. **Django admin mobile ceiling:** v4 custom admin screens will hit real rendering limits; scope v4 conservatively, do not over-promise mobile admin
3. **Session partial expiry across multiple slugs:** if a guest authenticates to multiple slugs and the session eventually expires, all slug authentications are lost together — expected behaviour, but owner should set guest expectations
4. **Django 6.0 background tasks (`django.tasks`):** available but not used for auto-archive; do not introduce it without explicit approval — cron + management command is sufficient and zero-dependency

---

*Distillate v2.4 — removed Docker entirely; setup via Makefile + bash scripts; `scripts/wait-for-db.sh` replaces Compose health check; Docker added to explicitly rejected list. Feed alongside product-brief-personal-hub.md into PRD or implementation planning.*
