---
title: 'e2e-coverage'
type: 'feature'
created: '2026-05-19'
status: 'done'
baseline_commit: '2cad862'
context: ['e2e/spec-e2e-admin-and-pages.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Existing E2E tests cover basic flows, but many critical scenarios from the product brief are untested: guest identity edge cases (name uniqueness, reclaim, min length, change name with update-claims), gated page edge cases (wrong password, 3 consecutive failure, archived/in-progress states), category locking edge cases, admin CRUD flows (create/edit/archive), usage statistics dashboard, contribution heatmap, and audit log with restore.

**Approach:** Add comprehensive Playwright E2E tests that cover every scenario from product-brief-personal-hub.md v2.4. No new fixtures needed — reuse existing conftest patterns.

## Boundaries & Constraints

**Always:**
- Tests use Polish text for assertions matching user-facing copy
- Tests are isolated — seed their own data and clean up after
- Reuse existing conftest helpers (`authenticate_guest`, `seed_gift_list`, `seed_event`, `seed_gift_list_multi`, `seed_event_multi`)
- Each test creates a unique guest name with UUID to avoid collisions
- Assert no content leak before both gates are passed

**Never:**
- Do not test race conditions with concurrent requests (unit-test pattern)
- Do not test auto-archive cron logic
- Do not run against production
- Do not commit test credentials

</frozen-after-approval>

## Code Map

- `e2e/test_admin.py` — extend with: admin CRUD (create gift list, create event, add items/roles), audit log view, usage statistics, contribution heatmap, password rotation, archive button
- `e2e/test_guest_pages.py` — extend with: wrong password error, empty list/event (in_progress), archived list/event, 3 consecutive failure hint, name validation (too short), name reclaim, header name display
- `e2e/test_claims.py` — extend with: edit claim with changed session name, update-claims action, category locking prevents individual assign, event edit assignment, race condition dialog elements

## Tasks & Acceptance

**Execution:**
- [x] `e2e/test_admin.py` — add TestAdminCRUD, TestAdminAuditLog, TestAdminUsageStats, TestAdminContributionHeatmap, TestAdminPasswordRotation, TestAdminArchive
- [x] `e2e/test_guest_pages.py` — add TestNameGateValidation, TestNameReclaim, TestWrongPassword, TestArchivedPages, TestInProgressPages, TestGuestSessionPersistence  
- [x] `e2e/test_claims.py` — add TestGiftEditFlowExtended, TestCategoryLocking, TestUpdateClaimsAction, TestEventEditAssignment, TestRaceConditionDialog

**Acceptance Criteria:**
- Given a running dev server with seeded data, when `pytest e2e/ -v` runs, all existing and new tests pass
- Guest sees "Imię musi mieć co najmniej 3 znaki." when name < 3 chars
- Guest sees "Nieprawidłowe hasło." on wrong password — no list content leaks
- Guest can reclaim an existing name via "To moje imię, loguję się ponownie"
- Admin can create a gift list with items and an event with categories/roles via admin
- Archived lists/events show "Ta lista jest obecnie zarchiwizowana" page
- Empty lists/events show "Trwa tworzenie listy" page
- Admin usage statistics loads with correct stats
- Contribution heatmap loads
- Category locking prevents individual role assignment
- Update Claims action renames all assignments
- Audit log is accessible in admin
- Session persists guest name across pages
- Password rotation via admin increments version

## Spec Change Log

- Initial creation — comprehensive coverage of product-brief-personal-hub.md v2.4 scenarios

## Suggested Review Order

1. `e2e/test_guest_pages.py` — new test classes for guest identity and gates
2. `e2e/test_claims.py` — extended claim/edit/update-claims tests
3. `e2e/test_admin.py` — admin CRUD, stats, heatmap, audit log

## Design Notes

**Name collision test:** Create a GuestName via the app first, then try to reuse it. Assert the "Ta nazwa jest już zajęta." error and the "To moje imię" reclaim option.

**Wrong password test:** Use a valid slug/password combo, then submit wrong password. Assert error message and no list content (title, items) in the response.

**In-progress/archived tests:** Use `_create_gift_list` with items=[] for empty list, and an additional fixture that sets `is_archived=True` for archived test.

**Conftest additions needed:** 
- `seed_archived_gift_list` — creates an archived gift list
- `seed_archived_event` — creates an archived event
- `seed_empty_gift_list` — creates a gift list with no items
- `seed_empty_event` — creates an event with no roles
These can be added to conftest.py

## Verification

**Commands:**
- `uv run pytest e2e/ -v --tb=short` — expected: all tests pass
- `uv run pytest e2e/test_admin.py -v --tb=short` — expected: admin tests pass
- `uv run pytest e2e/test_guest_pages.py -v --tb=short` — expected: guest page tests pass
- `uv run pytest e2e/test_claims.py -v --tb=short` — expected: claim tests pass