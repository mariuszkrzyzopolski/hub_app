# Handoff: Milestone v2 — Operational Polish

**Date:** 2026-05-19
**Status:** 🟢 Complete — 35/35 E2E tests passing
**Branch:** `master` (ahead of origin by 3 commits)

---

## Summary

Milestone v2 adds operational polish features that allow the owner to run live events confidently. The app is fully functional with both gift lists and event roles working end-to-end.

---

## What Was Implemented (v2)

### 1. Audit Log Restore Button
**Files:** `gifts/admin.py`, `events/admin.py`

- Both `GiftAuditLogAdmin` and `EventAuditLogAdmin` now have a `restore_button` callable column in `list_display`
- `get_urls()` override adds `<id>/restore/` endpoints
- One-click restore recreates the deleted `GiftClaim` / `RoleAssignment` from the audit log's snapshot data
- Bulk restore action also available: "Przywróć zaznaczone usunięte przypisania"
- Button is green (`#28a745`), only visible for entries where `is_deleted=True`

### 2. Share Info Panel
**Files:** `gifts/admin.py`, `events/admin.py`

- Added `share_info` as a `readonly_field` in both `GiftListAdmin` and `EventAdmin`
- Displays in a custom fieldset "Share Info" at the bottom of the change form
- Shows copyable stats: name, X/Y claimed, unique claimants, last activity, direct link
- Click-to-copy via `navigator.clipboard.writeText()`
- Stats format is plain-text, ready to paste into a chat message

### 3. Auto-Refresh via JSON-Count Poll
**Files:** `gifts/views.py`, `gifts/urls.py`, `gifts/templates/gifts/gift_list.html`, `events/views.py`, `events/urls.py`, `events/templates/events/event_roles.html`

- New JSON endpoints: `GET /gifts/<slug>/count/` and `GET /events/<slug>/count/`
- Return `{total, claimed}` / `{total, assigned}` as JSON
- Inline JS in templates polls every 10 seconds using `setInterval` + `fetch()`
- Updates only the progress text (`Postęp: X / Y`) — does NOT trigger page reload
- Preserves open dialogs (race condition dialog, delete confirmation)

### 4. Usage Statistics Dashboard
**Files:** `hub/admin_dashboard.py` (new), `templates/admin/usage_statistics.html` (new), `hub/urls.py`

- Custom admin view at `/admin/usage-statistics/` (requires staff login)
- Displays two tables: gift lists and events
- Each row shows: name, claimed/total with visual progress bar, completion %, unique claimants, last activity, active/archived status
- Sorted by completion percentage ascending
- Styled with green progress bars and strikethrough for archived items

### 5. Admin List View Improvements
- `date_hierarchy = 'timestamp'` added to both `GiftAuditLogAdmin` and `EventAuditLogAdmin`
- Search fields extended to include related model names (`gift_list__name`, `event__name`)
- Ordering set to `-timestamp` on all audit log admins
- Archive button via `get_urls()` on both `GiftListAdmin` and `EventAdmin` (`<id>/archive/` endpoint)

### 6. Name Collision Suggestion Factory
**Files:** `core/names_recommendation.py` — already live from v1

- `suggest_names(taken_name)` generates alternate suggestions like `Piotr_K`, `Piotr2`
- Shown in the name gate template when a name is taken
- Live-clickable suggestions in the name gate form

---

## Files Changed

| File | Status | Summary |
|---|---|---|
| `gifts/admin.py` | Modified (+142 lines) | Restore button, share info panel, archive button, list improvements |
| `gifts/urls.py` | Modified | Added `<slug:slug>/count/` route |
| `gifts/views.py` | Modified | Added `gift_count_json()` view |
| `gifts/templates/gifts/gift_list.html` | Modified | Added auto-refresh JS |
| `events/admin.py` | Modified (+143 lines) | Restore button, share info panel, archive button, list improvements |
| `events/urls.py` | Modified | Added `<slug:slug>/count/` route |
| `events/views.py` | Modified | Added `event_count_json()` view |
| `events/templates/events/event_roles.html` | Modified | Added auto-refresh JS |
| `hub/urls.py` | Modified | Added usage statistics route |
| `hub/admin_dashboard.py` | **New** | Usage statistics dashboard view |
| `templates/admin/usage_statistics.html` | **New** | Usage statistics template |

---

## URL Structure (Complete)

```
/                                    → Catalogue homepage
/admin/                              → Django admin (superuser only)
/admin/usage-statistics/             → Usage stats dashboard (staff only)

/gifts/                              → Public gift list index
/gifts/<slug>/                       → Gated gift list
/gifts/<slug>/count/                 → JSON count endpoint
/gifts/<slug>/claim/                 → POST claim
/gifts/<slug>/edit/<id>/             → POST edit
/gifts/<slug>/delete/<id>/           → POST delete
/gifts/<slug>/update-claims/         → POST rename assignee

/events/                             → Public event index
/events/<slug>/                      → Gated event board
/events/<slug>/count/                → JSON count endpoint
/events/<slug>/assign/               → POST assign role
/events/<slug>/assign-category/      → POST assign category
/events/<slug>/unclaim-category/     → POST unclaim category
/events/<slug>/edit/<id>/            → POST edit assignment
/events/<slug>/delete/<id>/          → POST delete assignment
/events/<slug>/update-claims/        → POST rename assignee
```

---

## Django Admin Endpoints

| Endpoint | Purpose |
|---|---|
| `/admin/gifts/giftlist/<id>/restore/` | Restore deleted gift claim |
| `/admin/gifts/giftlist/<id>/archive/` | Manually archive gift list |
| `/admin/events/event/<id>/restore/` | Restore deleted event assignment |
| `/admin/events/event/<id>/archive/` | Manually archive event |
| `/admin/usage-statistics/` | Usage statistics dashboard |

---

## Test Results

**35/35 tests passing** — run with `uv run pytest e2e/ -v`

```
test_admin.py ................... 9 passed  (login, gift lists, events)
test_claims.py .................. 10 passed (gift claims, event roles, category assign/unclaim)
test_guest_pages.py ............. 16 passed (homepage, indices, gates, auth flow)
```

---

## Database

- **PostgreSQL 16** via `hubapp` database
- All migrations applied (21 total)
- Tables: `core_guestname`, `gifts_*`, `events_*`, Django auth/admin/session
- Superuser: `warhir` / password from `.env`

---

## Known Issues / Pylance False Positives

The following Pylance errors are **false positives** — they work correctly at runtime:

- `Cannot assign to attribute "short_description"` — standard Django pattern for admin callables
- `Cannot assign to attribute "allow_tags"` — standard Django pattern
- `Cannot access attribute "items" for class "GiftList"` — Django reverse relation via `related_name`
- `Cannot access attribute "audit_logs" for class "GiftList"` — Django reverse relation

---

## Next Steps (v3+)

v3 focuses on **Guest Experience**:
- Clean frontend templates — full visual design pass
- Mobile optimisation — thumb-friendly layout and spacing
- All copy reviewed for clarity and brevity in Polish
- Homepage catalogue MVP — gift lists and events as distinct visual sections

v4 focuses on **Admin UX**:
- Custom admin screens within Django admin constraints
- Task-oriented shortcuts
- Mobile-friendlier admin flows

---

## Running the App

```bash
make install          # uv sync
make migrate          # Run migrations
make dev              # Start Gunicorn on port 8000
make createsuperuser  # Create admin user
make archive          # Run auto-archive cron
make check            # Django system check
```

To run E2E tests:
```bash
uv run pytest e2e/ -v