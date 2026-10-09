"""
Pytest configuration and fixtures for Personal Hub E2E tests.
"""
import os
import uuid
import subprocess
import pytest
from pathlib import Path

# Base project root
PROJECT_ROOT = Path(__file__).parent.parent


def get_env(key, default=None):
    """Read environment variable from .env file in project root."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(key) and "=" in line:
                _, _, value = line.partition("=")
                return value.strip().strip('"').strip("'")
    return os.environ.get(key, default)


@pytest.fixture(scope="session")
def base_url():
    """Return the base URL for the test server. Starts local server if not already running."""
    import socket
    import sys
    import time
    import urllib.request
    from urllib.parse import urlparse

    target_url = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8000")
    parsed = urlparse(target_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000

    def is_server_listening(h, p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((h, p)) == 0

    server_process = None
    if not is_server_listening(host, port):
        # Start server in background using gunicorn or runserver
        cmd = [sys.executable, "manage.py", "runserver", f"{host}:{port}", "--noreload"]
        server_process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ready = False
        start_time = time.time()
        while time.time() - start_time < 15:
            if is_server_listening(host, port):
                try:
                    with urllib.request.urlopen(f"{target_url}/", timeout=1):
                        ready = True
                        break
                except Exception:
                    pass
            time.sleep(0.2)
        if not ready:
            if server_process:
                server_process.terminate()
            raise RuntimeError(f"Could not connect to test server at {target_url}")

    yield target_url

    if server_process:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()


@pytest.fixture(scope="session")
def admin_credentials(base_url):
    """Return admin credentials loaded from .env."""
    username = get_env("ADMIN")
    password = get_env("ADMIN_PASSWORD")
    if not username or not password:
        pytest.skip("ADMIN and ADMIN_PASSWORD must be set in .env")
    return {"username": username, "password": password}


@pytest.fixture(scope="session")
def db_connection_params():
    """Return PostgreSQL connection params loaded from .env."""
    return {
        "dbname": get_env("DB_NAME", "personal_hub"),
        "user": get_env("DB_USER", "personal_hub"),
        "password": get_env("DB_PASSWORD", "personal_hub"),
        "host": get_env("DB_HOST", "localhost"),
        "port": get_env("DB_PORT", "5432"),
    }


def _run_django_command(*args):
    """Run a Django management command and return the result."""
    import sys
    result = subprocess.run(
        [sys.executable, "manage.py"] + list(args),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result


def _get_pg_connection(db_params):
    """Return a psycopg2 connection using params from .env."""
    import psycopg2
    return psycopg2.connect(
        dbname=db_params["dbname"],
        user=db_params["user"],
        password=db_params["password"],
        host=db_params["host"],
        port=db_params["port"],
    )


def _execute_sql(sql, db_params, params=None):
    """Execute raw SQL via psql (no parameterized queries needed for this path)."""
    cmd = [
        "psql",
        f"--dbname={db_params['dbname']}",
        f"--host={db_params['host']}",
        f"--port={db_params['port']}",
        f"--username={db_params['user']}",
        "--quiet",
        "-c", sql,
    ]
    env = os.environ.copy()
    env["PGPASSWORD"] = db_params["password"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result


def _create_gift_list(name, password, db_params, items=None):
    """Create a GiftList via raw SQL and return its slug."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    from django.contrib.auth.hashers import make_password
    hashed = make_password(password)

    if items is None:
        items = ['Test Gift Item']

    conn = _get_pg_connection(db_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gifts_giftlist
                    (slug, name, description, password_hash, password_version,
                     is_active, is_archived, event_date, created_at)
                VALUES (%s, %s, '', %s, 0, true, false, '2026-12-25', now())
                RETURNING id
                """,
                (slug, name, hashed),
            )
            gift_list_id = cur.fetchone()[0]
            # Seed test gift items
            for idx, item_name in enumerate(items):
                cur.execute(
                    """
                    INSERT INTO gifts_giftitem
                        (gift_list_id, name, description, "order")
                    VALUES (%s, %s, '', %s)
                    """,
                    (gift_list_id, item_name, idx),
                )
        conn.commit()
    finally:
        conn.close()
    return slug


def _create_event(name, password, db_params, categories=None):
    """Create an Event via raw SQL and return its slug."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    from django.contrib.auth.hashers import make_password
    hashed = make_password(password)

    if categories is None:
        categories = {'Test Category': ['Test Role']}

    conn = _get_pg_connection(db_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events_event
                    (slug, name, description, password_hash, password_version,
                     is_active, is_archived, event_date, created_at)
                VALUES (%s, %s, '', %s, 0, true, false, '2026-06-15', now())
                RETURNING id
                """,
                (slug, name, hashed),
            )
            event_id = cur.fetchone()[0]
            # Seed role categories and roles
            for cat_idx, (cat_name, roles) in enumerate(categories.items()):
                cur.execute(
                    """
                    INSERT INTO events_rolecategory
                        (event_id, name, "order")
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (event_id, cat_name, cat_idx),
                )
                category_id = cur.fetchone()[0]
                for role_idx, role_name in enumerate(roles):
                    cur.execute(
                        """
                        INSERT INTO events_role
                            (category_id, name, description, "order")
                        VALUES (%s, %s, '', %s)
                        """,
                        (category_id, role_name, role_idx),
                    )
        conn.commit()
    finally:
        conn.close()
    return slug


def _delete_model_table(slug, table, db_params):
    """Delete a GiftList or Event by slug using parameterized queries."""
    conn = _get_pg_connection(db_params)
    try:
        with conn.cursor() as cur:
            if table == "gifts_giftlist":
                cur.execute(
                    "DELETE FROM gifts_giftauditlog WHERE gift_list_id IN (SELECT id FROM gifts_giftlist WHERE slug = %s)",
                    (slug,),
                )
                cur.execute(
                    "DELETE FROM gifts_giftclaim WHERE item_id IN (SELECT id FROM gifts_giftitem WHERE gift_list_id IN (SELECT id FROM gifts_giftlist WHERE slug = %s))",
                    (slug,),
                )
                cur.execute(
                    "DELETE FROM gifts_giftitem WHERE gift_list_id IN (SELECT id FROM gifts_giftlist WHERE slug = %s)",
                    (slug,),
                )
                cur.execute("DELETE FROM gifts_giftlist WHERE slug = %s", (slug,))
            elif table == "events_event":
                cur.execute(
                    "DELETE FROM events_eventauditlog WHERE event_id IN (SELECT id FROM events_event WHERE slug = %s)",
                    (slug,),
                )
                cur.execute(
                    "DELETE FROM events_roleassignment WHERE role_id IN (SELECT id FROM events_role WHERE category_id IN (SELECT id FROM events_rolecategory WHERE event_id IN (SELECT id FROM events_event WHERE slug = %s)))",
                    (slug,),
                )
                cur.execute(
                    "DELETE FROM events_role WHERE category_id IN (SELECT id FROM events_rolecategory WHERE event_id IN (SELECT id FROM events_event WHERE slug = %s))",
                    (slug,),
                )
                cur.execute(
                    "DELETE FROM events_rolecategory WHERE event_id IN (SELECT id FROM events_event WHERE slug = %s)",
                    (slug,),
                )
                cur.execute("DELETE FROM events_event WHERE slug = %s", (slug,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seed_gift_list(db_connection_params):
    """Create a test GiftList and return its slug and password."""
    slug = _create_gift_list("Test Gift List", "testpass123", db_connection_params)
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "gifts_giftlist", db_connection_params)


@pytest.fixture
def seed_gift_list_multi(db_connection_params):
    """Create a test GiftList with multiple items and return its slug and password."""
    slug = _create_gift_list("Test Gift List Multi", "testpass123", db_connection_params,
                             items=["Book", "Watch", "Perfume", "Scarf"])
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "gifts_giftlist", db_connection_params)


@pytest.fixture
def seed_event(db_connection_params):
    """Create a test Event and return its slug and password."""
    slug = _create_event("Test Event", "testpass123", db_connection_params)
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "events_event", db_connection_params)


@pytest.fixture
def seed_event_multi(db_connection_params):
    """Create a test Event with multiple categories and roles."""
    categories = {
        "Food": ["Main Dish", "Dessert", "Drinks"],
        "Entertainment": ["DJ", "Games"],
    }
    slug = _create_event("Test Event Multi", "testpass123", db_connection_params,
                         categories=categories)
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "events_event", db_connection_params)


@pytest.fixture
def seed_archived_gift_list(db_connection_params):
    """Create an archived GiftList and return its slug."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    from django.contrib.auth.hashers import make_password
    hashed = make_password("testpass123")

    conn = _get_pg_connection(db_connection_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gifts_giftlist
                    (slug, name, description, password_hash, password_version,
                     is_active, is_archived, event_date, created_at)
                VALUES (%s, %s, '', %s, 0, true, true, '2026-01-01', now())
                RETURNING id
                """,
                (slug, "Archived Gift List", hashed),
            )
            gift_list_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO gifts_giftitem
                    (gift_list_id, name, description, "order")
                VALUES (%s, %s, '', 0)
                """,
                (gift_list_id, "Archived Item"),
            )
        conn.commit()
    finally:
        conn.close()
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "gifts_giftlist", db_connection_params)


@pytest.fixture
def seed_archived_event(db_connection_params):
    """Create an archived Event and return its slug."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    from django.contrib.auth.hashers import make_password
    hashed = make_password("testpass123")

    conn = _get_pg_connection(db_connection_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events_event
                    (slug, name, description, password_hash, password_version,
                     is_active, is_archived, event_date, created_at)
                VALUES (%s, %s, '', %s, 0, true, true, '2026-01-01', now())
                RETURNING id
                """,
                (slug, "Archived Event", hashed),
            )
            event_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO events_rolecategory
                    (event_id, name, "order")
                VALUES (%s, %s, 0)
                RETURNING id
                """,
                (event_id, "Archived Category"),
            )
            category_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO events_role
                    (category_id, name, description, "order")
                VALUES (%s, %s, '', 0)
                """,
                (category_id, "Archived Role"),
            )
        conn.commit()
    finally:
        conn.close()
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "events_event", db_connection_params)


@pytest.fixture
def seed_empty_gift_list(db_connection_params):
    """Create a GiftList with no items (in-progress state)."""
    slug = _create_gift_list("Empty Gift List", "testpass123", db_connection_params, items=[])
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "gifts_giftlist", db_connection_params)


@pytest.fixture
def seed_empty_event(db_connection_params):
    """Create an Event with a category but no roles (in-progress state)."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    from django.contrib.auth.hashers import make_password
    hashed = make_password("testpass123")

    conn = _get_pg_connection(db_connection_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events_event
                    (slug, name, description, password_hash, password_version,
                     is_active, is_archived, event_date, created_at)
                VALUES (%s, %s, '', %s, 0, true, false, '2026-06-15', now())
                RETURNING id
                """,
                (slug, "Empty Event", hashed),
            )
            event_id = cur.fetchone()[0]
            # Category with no roles — will be excluded from queryset and trigger in_progress
            cur.execute(
                """
                INSERT INTO events_rolecategory
                    (event_id, name, "order")
                VALUES (%s, %s, 0)
                """,
                (event_id, "Empty Category"),
            )
        conn.commit()
    finally:
        conn.close()
    yield {"slug": slug, "password": "testpass123"}
    _delete_model_table(slug, "events_event", db_connection_params)


@pytest.fixture
def seed_gift_list_with_claim(db_connection_params):
    """Create a GiftList with one pre-claimed item."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    from django.contrib.auth.hashers import make_password
    hashed = make_password("testpass123")

    conn = _get_pg_connection(db_connection_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gifts_giftlist
                    (slug, name, description, password_hash, password_version,
                     is_active, is_archived, event_date, created_at)
                VALUES (%s, %s, '', %s, 0, true, false, '2026-12-25', now())
                RETURNING id
                """,
                (slug, "Pre-claimed List", hashed),
            )
            gift_list_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO gifts_giftitem
                    (gift_list_id, name, description, "order")
                VALUES (%s, %s, '', 0)
                RETURNING id
                """,
                (gift_list_id, "Claimed Item"),
            )
            item_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO gifts_giftclaim
                    (item_id, assignee_name, session_id, claimed_at, updated_at)
                VALUES (%s, %s, %s, now(), now())
                """,
                (item_id, "PreExistingClaimant", "session-pre-existing"),
            )
        conn.commit()
    finally:
        conn.close()
    yield {"slug": slug, "password": "testpass123", "claimant": "PreExistingClaimant"}
    _delete_model_table(slug, "gifts_giftlist", db_connection_params)


@pytest.fixture(scope="session")
def playwright_browser():
    """
    Launch a Playwright browser (chromium) for the test session.
    Installs browsers on first run if needed.
    """
    from playwright.sync_api import sync_playwright

    # Ensure browser is installed
    import sys
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        cwd=PROJECT_ROOT,
        capture_output=True,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(playwright_browser):
    """Create a new browser page for each test."""
    context = playwright_browser.new_context()
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


def authenticate_guest(page, base_url, slug, guest_name, password, app_type="gifts"):
    """Helper: navigate to a gated page and pass both name and password gates."""
    page.goto(f"{base_url}/{app_type}/{slug}/")
    page.wait_for_load_state("networkidle")
    # Name gate
    page.fill("input[name=guest_name]", guest_name)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    # Password gate
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")