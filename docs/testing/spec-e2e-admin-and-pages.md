---
title: 'e2e-admin-and-pages'
type: 'feature'
created: '2026-05-18'
status: 'done'
baseline_commit: 'c4c61f9'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** No automated verification that the admin panel and public/gated pages work correctly after setup or code changes.

**Approach:** Add Playwright-based end-to-end tests that verify admin login, admin panel pages, and the full guest flow (homepage → name gate → password gate → page content) for both gifts and events.

## Boundaries & Constraints

**Always:**
- Tests use `ADMIN` and `ADMIN_PASSWORD` from `.env` for superuser authentication
- Tests run against a live dev server (started via `make dev` or `uv run`)
- Tests are isolated — they seed their own data and clean up after
- All user-facing copy is Polish — test assertions use Polish text

**Ask First:** N/A

**Never:**
- Do not test race conditions or concurrent claims
- Do not test auto-archive cron logic
- Do not run against production
- Do not commit test credentials — use env vars only

</frozen-after-approval>

## Code Map

- `pyproject.toml` -- add test dependencies
- `e2e/` -- test root (new directory)
- `e2e/conftest.py` -- pytest fixtures: browser, live server URL, admin credentials, DB seeding helpers
- `e2e/test_admin.py` -- admin panel tests
- `e2e/test_guest_pages.py` -- homepage, gift index, event index, gate pages
- `.env.template` -- document `ADMIN` and `ADMIN_PASSWORD` vars

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- add `pytest` and `playwright` dependencies
- [x] `pyproject.toml` -- add `pytest-django` dependency
- [x] `e2e/conftest.py` -- create fixtures: `browser`, `admin_credentials`, `seed_gift_list`, `seed_event`
- [x] `e2e/test_admin.py` -- test admin login page, login with valid credentials, login with invalid credentials, admin home, Gift Lists list page, Events list page
- [x] `e2e/test_guest_pages.py` -- test homepage loads, gifts index loads, events index loads, gift list password gate, gift list name gate, event password gate, event name gate
- [ ] `.env.template` -- SKIPPED: permission denied on `.env.template` (user to add manually)

**Acceptance Criteria:**
- Given a running dev server, when `pytest e2e/` runs, all tests pass
- Given valid admin credentials in `.env`, when the admin logs in, the Django admin index page loads with "Django administration" heading
- Given valid admin credentials, when the admin visits `/admin/gifts/giftlist/`, the Gift Lists admin page loads
- Given valid admin credentials, when the admin visits `/admin/events/event/`, the Events admin page loads
- Given no session, when a guest visits `/gifts/<slug>/`, only the password form renders (no list title or items visible)
- Given no session, when a guest visits `/events/<slug>/`, only the password form renders (no event title or roles visible)
- Given an authenticated slug but no name, when a guest visits `/gifts/<slug>/`, the name gate form renders
- Given an authenticated slug but no name, when a guest visits `/events/<slug>/`, the name gate form renders

## Spec Change Log

- **Review round 1** — SQL injection: replaced f-string SQL in `_create_gift_list`, `_create_event`, `_delete_model_table` with parameterized queries via `psycopg2`. Also replaced `psql` subprocess calls with direct `psycopg2` connections for create functions.
- **Review round 1** — Unused `time` import removed from conftest.py.
- **Review round 1** — `page` fixture wrapped in try/finally for safe teardown on exception.
- **Review round 1** — `test_admin_login_success`: added `wait_until="load"` and `timeout=10000` to `wait_for_url`; added assertion that login form (`#id_username`) is gone after submit to prevent false passes.
- **Review round 1** — `wait_for_url` timeout added to all admin login tests (10s default is not explicit enough).
- **Review round 1** — `test_homepage_has_gifts_link` / `test_homepage_has_events_link`: fixed `.first` accessor returning a locator with `.count()` returning 1 always. Replaced with direct `.count()` on locator.
- **Review round 1** — `pyproject.toml`: changed `dev-dependencies` to `[project.optional-dependencies] test = [...]` per PEP 621 spec.
- **Review round 1** — KEEP: parameterized query pattern, try/finally cleanup, timeout on waits, psycopg2 direct connection for DB seeding.

## Suggested Review Order

1. `e2e/conftest.py` — review SQL seeding pattern and fixture cleanup
2. `e2e/test_admin.py` — review admin test assertions and wait patterns
3. `e2e/test_guest_pages.py` — review gate test coverage and auth flow tests
4. `pyproject.toml` — review optional test dependencies

## Design Notes

**Playwright vs Selenium:** Playwright has better async handling, auto-waiting, and cross-browser support. It's the modern choice for Django E2E tests.

**Fixtures pattern:** `seed_gift_list` creates a GiftList with password "testpass123" and returns the slug. Same for `seed_event`. Each test gets a fresh slug to avoid collision.

**Admin auth:** Use Playwright's `page.fill()` on the Django admin login form (`#id_username`, `#id_password`) and `page.click('input[type=submit]')`. Store the session cookie so subsequent requests in the same test are authenticated.

**Gate assertion pattern:** For password gate, assert `page.content()` contains the password form and does NOT contain the list/event title. Use `page.locator()` to check form presence.

**Cleanup:** Each fixture uses Django's ORM directly via `uv run python -c "..."` or a management command to create test data, and a teardown fixture to delete it after the test.

## Verification

**Commands:**
- `cd e2e && uv run playwright install chromium --with-deps` -- install browser
- `uv run pytest e2e/ -v` -- expected: all tests pass

**Manual checks (if no CLI):**
- Open `http://localhost:8000/admin/` in browser, log in with `.env` credentials, verify Gift Lists and Events apps are visible
- Visit `http://localhost:8000/gifts/` and `http://localhost:8000/events/` and verify they load without error