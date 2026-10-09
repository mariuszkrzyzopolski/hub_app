# Personal Hub — Project Reference

> Generated from product-brief-personal-hub.md + current app state (v5 implemented)
> Generated: 2026-05-19

---

## 1. Overview

**Personal Hub** is a lightweight, self-hosted Django web application that helps coordinate social occasions. It manages gift lists and event role assignments through a shared-link, password-gated, no-accounts model.

| Attribute | Value |
|---|---|
| Stack | Python 3.12 · Django 6.0.5 · uv · PostgreSQL 16 |
| Architecture | Catalogue pattern — `core/` is shared base, `gifts/` and `events/` are independent mini-apps |
| Guest model | Session-scoped unique name; no accounts, no email, no tracking |
| Admin | Django built-in admin — single superuser |
| Language | Polish (user-facing), English (admin interface) |
| Production | Gunicorn + PostgreSQL; Makefile + bash scripts (no Docker) |

---

## 2. Project Structure

```
hub_app/
├── pyproject.toml                     # Dependencies, Python version, project metadata
├── Makefile                           # install, dev, migrate, createsuperuser, etc.
├── uv.lock                            # Reproducible dependency lockfile
├── manage.py                          # Django management entry point
├── hub/                               # Django project package
│   ├── settings.py                    # Configuration
│   ├── urls.py                        # Root URL configuration
│   ├── wsgi.py                        # WSGI application for Gunicorn
│   ├── views.py                       # Homepage view
│   ├── admin_dashboard.py             # Usage statistics dashboard (admin)
│   └── contribution_heatmap.py        # Contribution heatmap feature
├── core/                              # Shared catalogue layer
│   ├── models.py                      # PasswordGatedModel, AuditLogEntry (abstract), GuestName
│   ├── mixins.py                      # PasswordGatedViewMixin
│   ├── session.py                     # get/set guest name, authenticated_slugs helpers
│   ├── names_recommendation.py        # Name collision suggestion factory
│   ├── management/commands/
│   │   ├── archive_expired.py         # Auto-archives lists/events 14 days past event_date
│   │   └── wait_for_db.py             # DB readiness check script
│   ├── templates/core/
│   │   ├── base.html                  # Base template — header with name display/change
│   │   ├── password_gate.html         # Password form before accessing gated pages
│   │   ├── name_gate.html             # Name entry form (first visit)
│   │   ├── archived.html              # Displayed when list/event is archived
│   │   └── in_progress.html           # Displayed when list/event has zero items
│   └── static/
│       └── style.css                  # Global styles
├── gifts/                             # Gift list mini-app
│   ├── models.py                      # GiftList, GiftItem, GiftClaim, GiftAuditLog
│   ├── views.py                       # Gift list views + claim/edit/delete/update-claims
│   ├── urls.py                        # Gift URL routing
│   ├── admin.py                       # Custom Django admin for gifts
│   └── templates/gifts/
│       ├── gift_index.html            # Public index of active gift lists
│       └── gift_list.html             # Single gift list page (gated)
├── events/                            # Event roles mini-app
│   ├── models.py                      # Event, RoleCategory, Role, RoleAssignment, EventAuditLog
│   ├── views.py                       # Event views + assign/assign-category/unclaim-category/edit/delete/update-claims
│   ├── urls.py                        # Event URL routing
│   ├── admin.py                       # Custom Django admin for events
│   └── templates/events/
│       ├── event_index.html           # Public index of active events
│       └── event_roles.html           # Single event role board page (gated)
├── templates/
│   ├── home.html                      # Homepage catalogue
│   └── admin/
│       ├── base_site.html             # Customised admin base template
│       ├── index.html                 # Customised admin index
│       ├── usage_statistics.html      # Usage statistics dashboard
│       └── contribution_heatmap.html  # Contribution heatmap (v5)
├── scripts/
│   └── wait-for-db.sh                 # Bash script — polls PostgreSQL before migrations
├── e2e/                               # End-to-end tests
│   ├── conftest.py                    # Test configuration and fixtures
│   ├── test_admin.py                  # Admin interface tests
│   ├── test_claims.py                 # Claim/assignment tests
│   ├── test_guest_pages.py            # Guest page access tests
│   └── spec-e2e-*.md                  # E2E test specifications
├── .env                               # Environment variables (secret key, DB config)
└── .env.template                      # Environment variable template
```

---

## 3. Architecture & Design Decisions

### 3.1 Catalogue Architecture

```
                         ┌─────────────────────────────┐
                         │       hub/ (project)         │
                         │  urls.py → roothome, admin   │
                         └──────┬──────────────────────┘
                                │ includes
              ┌─────────────────┼─────────────────┐
              │                 │                 │
     ┌────────▼──────┐  ┌──────▼───────┐  ┌─────▼──────┐
     │   core/       │  │   gifts/     │  │   events/  │
     │ (shared base) │  │ (mini-app 1) │  │(mini-app 2)│
     └───────────────┘  └──────────────┘  └────────────┘
```

- `core/` provides abstract base models, authentication mixins, session helpers, name recommendations, and shared templates
- `gifts/` and `events/` are independent mini-apps that extend core abstractions
- Future mini-apps plug into the same catalogue pattern

### 3.2 Authentication & Access

**Guest authentication is session-based, multi-layered:**

1. **Name gate** — On first visit to any page, guest enters a globally unique name (3–200 chars, stored in `GuestName` model)
2. **Password gate** — Each list/event has its own password (4–20 chars, stored hashed). `PasswordGatedViewMixin` enforces this
3. **Slug-level access** — After authenticating to a list/event, the slug + current `password_version` is stored in the session

**Session structure:**

```python
request.session['guest_name'] = 'Piotr'
request.session['authenticated_slugs'] = [
    {'slug': 'urodziny-kaski', 'password_version': 3},
    {'slug': 'grill-2026', 'password_version': 1},
]
```

**Key security rules:**
- `request.session.modified = True` must be set after mutating `authenticated_slugs` (Django doesn't detect list mutations)
- `@method_decorator(never_cache, name='dispatch')` on `PasswordGatedViewMixin` — all gated pages send `Cache-Control: no-store`
- Password rotation increments `password_version` via `F('password_version') + 1` — stale sessions must re-authenticate
- Three consecutive failed password attempts on a slug are logged to the audit log

### 3.3 Race Condition Handling

| Scenario | Mechanism |
|---|---|
| Gift claim concurrency | `select_for_update(nowait=True)` — immediate fail, dialog: *"Ten prezent został właśnie zajęty. Odśwież stronę i wybierz inny."* |
| Category role assignment | `select_for_update()` with `order_by('id')` in atomic transaction — consistent lock ordering prevents deadlocks |
| Name uniqueness race | Three-layer defence: Python check → DB unique constraint → `transaction.atomic()` + `IntegrityError` catch |

### 3.4 Category Locking (Events)

- When a guest uses **"Assign Category"**, all unassigned roles in the category get `via_category=True`
- While any role in a category has `via_category=True`, individual roles are locked (no edit/claim)
- **"Unclaim Category"** clears all `via_category=True` flags and unlocks individual roles

---

## 4. Data Model

### 4.1 Core (Abstract Base Models)

```
PasswordGatedModel (abstract)
├── slug: CharField(unique, max_length=200)
├── name: CharField(max_length=200)
├── description: TextField(blank=True)
├── password_hash: CharField(max_length=128)
├── password_version: IntegerField(default=1)
├── is_active: BooleanField(default=True)
├── is_archived: BooleanField(default=False)
├── event_date: DateField(null=True, blank=True)
└── created_at: DateTimeField(auto_now_add=True)

AuditLogEntry (abstract)
├── action: CharField(max_length=50)
├── assignee_name: CharField(max_length=200, blank=True)
├── session_id: CharField(max_length=100, blank=True)
├── timestamp: DateTimeField(auto_now_add=True)
├── is_deleted: BooleanField(default=False)
└── restored_at: DateTimeField(null=True, blank=True)

GuestName
├── name: CharField(max_length=200, unique=True)
└── created_at: DateTimeField(auto_now_add=True)
```

### 4.2 Gifts

```
GiftList(PasswordGatedModel)
├── [inherited fields]
└── items → GiftItem[]

GiftItem
├── list: FK → GiftList (CASCADE)
├── name: CharField(max_length=200)
├── description: TextField(blank=True)
└── order: IntegerField(default=0)

GiftClaim
├── item: OneToOneField → GiftItem (CASCADE)
├── assignee_name: CharField(max_length=200)
├── session_id: CharField(max_length=100)
├── claimed_at: DateTimeField(auto_now_add=True)
└── updated_at: DateTimeField(auto_now=True)

GiftAuditLog(AuditLogEntry)
├── [inherited fields]
├── list: FK → GiftList (CASCADE)
├── item: FK → GiftItem (nullable)
├── item_name: CharField(max_length=200, blank=True)
├── item_description: TextField(blank=True)
├── item_order: IntegerField(default=0)
└── assignee_session_id: CharField(max_length=100, blank=True)
```

### 4.3 Events

```
Event(PasswordGatedModel)
├── [inherited fields]
└── categories → RoleCategory[]

RoleCategory
├── event: FK → Event (CASCADE)
├── name: CharField(max_length=200)
├── order: IntegerField(default=0)
└── roles → Role[]

Role
├── category: FK → RoleCategory (CASCADE)
├── name: CharField(max_length=200)
├── description: TextField(blank=True)
└── order: IntegerField(default=0)

RoleAssignment
├── role: OneToOneField → Role (CASCADE)
├── assignee_name: CharField(max_length=200)
├── session_id: CharField(max_length=100)
├── via_category: BooleanField(default=False)
├── assigned_at: DateTimeField(auto_now_add=True)
└── updated_at: DateTimeField(auto_now=True)

EventAuditLog(AuditLogEntry)
├── [inherited fields]
├── event: FK → Event (CASCADE)
├── role: FK → Role (nullable)
├── role_name: CharField(max_length=200, blank=True)
├── role_description: TextField(blank=True)
├── role_order: IntegerField(default=0)
├── category_name: CharField(max_length=200, blank=True)
└── assignee_session_id: CharField(max_length=100, blank=True)
```

---

## 5. URL Structure & Views

| URL | View | Auth | Description |
|---|---|---|---|
| `/` | `hub.views.HomePageView` | Public | Homepage catalogue |
| `/gifts/` | `gifts.views.GiftIndexView` | Public | Active gift lists + progress |
| `/gifts/<slug>/` | `gifts.views.GiftListView` | Password + name | Gift list detail |
| `/gifts/<slug>/claim/` | `gifts.views.ClaimGiftView` | Password + name | POST — claim a gift |
| `/gifts/<slug>/edit/<int:id>/` | `gifts.views.EditClaimView` | Password + name | POST — edit claimant |
| `/gifts/<slug>/delete/<int:id>/` | `gifts.views.DeleteClaimView` | Password + name | POST — delete claim |
| `/gifts/<slug>/update-claims/` | `gifts.views.UpdateClaimsView` | Password + name | POST — rename all claims |
| `/events/` | `events.views.EventIndexView` | Public | Active events + progress |
| `/events/<slug>/` | `events.views.EventRolesView` | Password + name | Event role board |
| `/events/<slug>/assign/` | `events.views.AssignRoleView` | Password + name | POST — assign single role |
| `/events/<slug>/assign-category/` | `events.views.AssignCategoryView` | Password + name | POST — claim entire category |
| `/events/<slug>/unclaim-category/` | `events.views.UnclaimCategoryView` | Password + name | POST — release category |
| `/events/<slug>/edit/<int:id>/` | `events.views.EditAssignmentView` | Password + name | POST — edit assignee |
| `/events/<slug>/delete/<int:id>/` | `events.views.DeleteAssignmentView` | Password + name | POST — delete assignment |
| `/events/<slug>/update-claims/` | `events.views.UpdateClaimantView` | Password + name | POST — rename all assignments |
| `/admin/` | Django admin | Superuser | Management interface |

---

## 6. Key Implementation Details

### 6.1 PasswordGatedViewMixin

File: `core/mixins.py`

- Overrides `dispatch()` (not `get()`) — blocks POST endpoints too
- Must be **leftmost** in MRO: `class MyView(PasswordGatedViewMixin, BaseView)`
- Checks session for slug + matching `password_version`
- Applies `@method_decorator(never_cache, name='dispatch')` — `Cache-Control: no-store` on all responses
- On password submission: validates hashed password, stores slug + version in session, sets `session.modified = True`
- On version mismatch: clears stale slug entry from session, forces re-authentication

### 6.2 Session Helpers

File: `core/session.py`

```python
def get_guest_name(request) -> str | None
def set_guest_name(request, name: str) -> None
def is_authenticated_to_slug(request, slug: str) -> bool
def add_slug_to_session(request, slug: str, password_version: int) -> None
def get_authenticated_slugs(request) -> list
```

All mutation helpers call `request.session.modified = True` automatically.

### 6.3 Name Recommendation

File: `core/names_recommendation.py`

Suggests alternatives when a name is taken:
- Append underscore + first letter of surname if surname exists: `"Piotr_K"`
- Append incremental number: `"Piotr2"`, `"Piotr3"`
- Use the factory pattern — configurable via strategy

### 6.4 Auto-Archive

File: `core/management/commands/archive_expired.py`

- Queries all `is_archived=False` records where `event_date < date.today() - timedelta(days=14)`
- Sets `is_archived = True`
- Called via cron daily: `manage.py archive_expired`

### 6.5 Admin Customisation

- **Password save handling:** `save_model()` calls `check_password()` before re-hashing — avoids double-hashing
- **Audit log restore:** `get_urls()` override adds restore endpoint; `list_display` includes callable anchor column
- **Password rotation:** Uses `F('password_version') + 1` for atomic increment
- **Slug generation:** `prepopulated_fields` in admin + `python-slugify` in `save()` for correct non-ASCII transliteration
- **Custom admin templates:** `base_site.html`, `index.html`, `usage_statistics.html` (v2), `contribution_heatmap.html` (v5)

### 6.6 Contribution Heatmap (v5)

File: `hub/contribution_heatmap.py`

- Owner-facing view of which guests claimed/assigned the most
- Aggregates data from `GiftAuditLog` and `EventAuditLog`
- Displayed in admin interface

### 6.7 Usage Statistics (v2)

File: `hub/admin_dashboard.py`

- Per list/event: completion %, unique claimant names, last activity date
- Displayed in custom admin dashboard

---

## 7. Milestone Status

| Milestone | Status | Key Deliverables |
|---|---|---|
| **v1 — Functional Core** | ✅ Complete | Session auth, guest names, password gating, gift list CRUD, event role CRUD with category locking, race condition handling, auto-archive, audit log, admin CRUD, password rotation |
| **v2 — Operational Polish** | ✅ Complete | Audit log restore button, name suggestions, share info panel, auto-refresh polling, usage statistics dashboard, admin list view improvements |
| **v3 — Guest Experience** | ✅ Complete | Full visual design pass, mobile optimisation, Polish copy review, homepage catalogue |
| **v4 — Admin UX** | ✅ Complete | Custom admin screens, task-oriented shortcuts, admin mobile-friendliness improvements, customised `admin/index.html` and `admin/base_site.html` |
| **v5 — Optional Extensions** | ✅ Complete | Contribution heatmap (owner-facing), statistics extensions, `hub/admin_dashboard.py`, `hub/contribution_heatmap.py` |

---

## 8. Setup & Operations

### Prerequisites

- Python 3.12+
- PostgreSQL 16
- `uv` (Python package manager)
- `make`

### Commands

| Command | Action |
|---|---|
| `make install` | `uv sync` — install dependencies from `uv.lock` |
| `make dev` | Start Gunicorn + PostgreSQL, run migrations |
| `make migrate` | `python manage.py migrate` |
| `make createsuperuser` | Create Django superuser |
| `make shell` | Django shell |
| `./scripts/wait-for-db.sh` | Poll PostgreSQL until ready (used by Makefile) |

### Environment Variables (`.env`)

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `DJANGO_DEBUG` | Debug mode (True for dev) |
| `DJANGO_ALLOWED_HOSTS` | Allowed hostnames |

### Cron Job

```
0 2 * * * cd /path/to/hub_app && /path/to/uv run manage.py archive_expired
```

---

## 9. Testing

### E2E Tests

Location: `e2e/`

| File | Description |
|---|---|
| `conftest.py` | Test configuration, fixtures, and helpers |
| `test_admin.py` | Admin CRUD, password management, audit log, restore, statistics |
| `test_claims.py` | Gift claims, role assignments, category locking, race conditions |
| `test_guest_pages.py` | Authentication flow, name gating, password gating, page access |

Test specifications:
- `spec-e2e-admin-and-pages.md` — Admin + page rendering coverage
- `spec-e2e-coverage.md` — Overall test coverage tracking

---

## 10. Dependencies

Key Python packages (from `pyproject.toml`):

| Package | Purpose |
|---|---|
| Django 6.0.5 | Web framework |
| psycopg 3 | PostgreSQL adapter |
| python-slugify | Slug generation with Polish character support |
| gunicorn | Production WSGI server |
| environs | Environment variable management |

---

## 11. Out of Scope (permanent)

- Real-time updates / WebSockets / Django Channels
- User accounts or login system
- Email notifications
- Multi-admin support
- Public sharing without password
- Read-only guest mode
- Comments or messaging
- Mobile native app
- English UI (Polish-only for guests)
- Django i18n system
- Docker (removed in brief v2.4)