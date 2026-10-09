"""
E2E tests for guest-facing public and gated pages.

Covers:
- Homepage, gift index, event index
- Name gate and password gate sequencing
- Name validation (min length, uniqueness, reclaim)
- Wrong password handling
- Archived list/event pages
- Empty/in-progress list/event pages
- Session persistence across pages
"""
import uuid
import pytest
from conftest import authenticate_guest


class TestHomepage:
    """Test the hub homepage (catalogue directory)."""

    def test_homepage_loads(self, page, base_url):
        """Homepage is accessible and contains expected content."""
        page.goto(f"{base_url}/")
        assert page.locator("body").count() == 1

    def test_homepage_has_gifts_link(self, page, base_url):
        """Homepage contains a link to the gifts index."""
        page.goto(f"{base_url}/")
        assert page.locator('a[href*="/gifts/"]').count() > 0

    def test_homepage_has_events_link(self, page, base_url):
        """Homepage contains a link to the events index."""
        page.goto(f"{base_url}/")
        assert page.locator('a[href*="/events/"]').count() > 0


class TestGiftIndex:
    """Test the public gift lists index page."""

    def test_gifts_index_loads(self, page, base_url):
        """The /gifts/ page loads without error."""
        response = page.goto(f"{base_url}/gifts/")
        assert response.status == 200

    def test_gifts_page_renders(self, page, base_url):
        """The /gifts/ page renders HTML without error."""
        page.goto(f"{base_url}/gifts/")
        assert len(page.content()) > 0


class TestEventIndex:
    """Test the public events index page."""

    def test_events_index_loads(self, page, base_url):
        """The /events/ page loads without error."""
        response = page.goto(f"{base_url}/events/")
        assert response.status == 200
        assert page.locator("body").count() == 1

    def test_events_page_renders(self, page, base_url):
        """The /events/ page renders HTML without error."""
        page.goto(f"{base_url}/events/")
        assert len(page.content()) > 0


class TestGiftListGates:
    """Test name gate and password gate on a gift list page.

    PasswordGatedViewMixin fires the name gate FIRST (guest has no session name),
    then the password gate after a valid name is set.
    """

    def test_gift_list_name_gate_shows_first(self, page, base_url, seed_gift_list):
        """On fresh visit, the name gate renders before the password gate."""
        slug = seed_gift_list["slug"]
        response = page.goto(f"{base_url}/gifts/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        assert page.locator("input[name=guest_name]").count() == 1
        assert "Test Gift List" not in page.content()
        assert page.locator("input[name=password]").count() == 0

    def test_gift_list_password_gate_shows_after_name(
        self, page, base_url, seed_gift_list
    ):
        """After entering a valid name, the password gate renders."""
        slug = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"TG{uuid.uuid4().hex[:6]}"
        response = page.goto(f"{base_url}/gifts/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert page.locator("input[name=password]").count() == 1
        assert "Test Gift List" not in content

    def test_gift_list_no_content_before_full_auth(
        self, page, base_url, seed_gift_list
    ):
        """Even after entering name, list content is hidden until password is entered."""
        slug = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"TG{uuid.uuid4().hex[:6]}"
        response = page.goto(f"{base_url}/gifts/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert page.locator("input[name=password]").count() == 1
        assert "Zarezerwuj" not in page.content()


class TestEventGates:
    """Test name gate and password gate on an event page.

    Same pattern as gift list gates.
    """

    def test_event_name_gate_shows_first(self, page, base_url, seed_event):
        """On fresh visit, the name gate renders before the password gate."""
        slug = seed_event["slug"]
        response = page.goto(f"{base_url}/events/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        assert page.locator("input[name=guest_name]").count() == 1
        assert "Test Event" not in page.content()
        assert page.locator("input[name=password]").count() == 0

    def test_event_password_gate_shows_after_name(self, page, base_url, seed_event):
        """After entering a valid name, the password gate renders."""
        slug = seed_event["slug"]
        password = seed_event["password"]
        guest_name = f"TE{uuid.uuid4().hex[:6]}"
        response = page.goto(f"{base_url}/events/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert page.locator("input[name=password]").count() == 1
        assert "Test Event" not in content

    def test_event_no_content_before_full_auth(self, page, base_url, seed_event):
        """Even after name, event content is hidden until password entered."""
        slug = seed_event["slug"]
        password = seed_event["password"]
        guest_name = f"TE{uuid.uuid4().hex[:6]}"
        response = page.goto(f"{base_url}/events/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert page.locator("input[name=password]").count() == 1
        assert "Przypisz" not in page.content()


class TestGiftListAuthenticatedFlow:
    """Test the full guest flow through both gates on a gift list."""

    def test_gift_list_full_auth_flow(self, page, base_url, seed_gift_list):
        """Guest enters name then password, then sees the gift list content."""
        slug = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"TG{uuid.uuid4().hex[:6]}"

        response = page.goto(f"{base_url}/gifts/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=password]", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        content = page.content()
        assert "Test Gift List" in content
        assert guest_name in page.locator("header").inner_text()


class TestEventAuthenticatedFlow:
    """Test the full guest flow through both gates on an event."""

    def test_event_full_auth_flow(self, page, base_url, seed_event):
        """Guest enters name then password, then sees the event roles content."""
        slug = seed_event["slug"]
        password = seed_event["password"]
        guest_name = f"TE{uuid.uuid4().hex[:6]}"

        response = page.goto(f"{base_url}/events/{slug}/")
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=password]", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        content = page.content()
        assert "Test Event" in content
        assert guest_name in page.locator("header").inner_text()


class TestNameGateValidation:
    """Test name gate edge cases: min length, uniqueness, reclaim."""

    def test_name_too_short_shows_error(self, page, base_url, seed_gift_list):
        """Entering a name shorter than 3 characters shows validation error."""
        slug = seed_gift_list["slug"]
        page.goto(f"{base_url}/gifts/{slug}/")
        page.wait_for_load_state("networkidle")

        # HTML5 minlength="3" blocks client-side submission; bypass it
        # by removing the minlength attribute then submit via JS
        page.evaluate("""() => {
            document.querySelector('input[name=guest_name]').removeAttribute('minlength');
        }""")
        page.fill("input[name=guest_name]", "Ab")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        content = page.content()
        assert "Imię musi mieć co najmniej 3 znaki" in content
        # Should still be on the name gate — no password field
        assert page.locator("input[name=guest_name]").count() == 1
        assert page.locator("input[name=password]").count() == 0

    def test_name_taken_shows_suggestions(self, page, base_url, seed_gift_list):
        """Using a name that's already taken shows error and suggestions."""
        slug = seed_gift_list["slug"]
        guest_name = f"NT{uuid.uuid4().hex[:6]}"

        # First visit: register the name
        page.goto(f"{base_url}/gifts/{slug}/")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        # Now on password gate, we have a valid name registered

        # Second visit in a new context (different session) with the same name
        page2 = base_url  # We need a fresh context - test in new page
        context = page.context.browser.new_context()
        page2 = context.new_page()
        try:
            page2.goto(f"{base_url}/gifts/{slug}/")
            page2.wait_for_load_state("networkidle")
            page2.fill("input[name=guest_name]", guest_name)
            page2.click("button[type=submit]")
            page2.wait_for_load_state("networkidle")

            content = page2.content()
            assert "Ta nazwa jest już zajęta" in content
            # Reclaim link should be visible
            assert "To moje imię" in content or "loguję się ponownie" in content
        finally:
            context.close()

    def test_name_reclaim_works(self, page, base_url, seed_gift_list):
        """Guest can reclaim an existing name via 'To moje imię, loguję się ponownie'."""
        slug = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"NR{uuid.uuid4().hex[:6]}"

        # First visit: register name and pass password
        page.goto(f"{base_url}/gifts/{slug}/")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=password]", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert guest_name in page.content()

        # Now in a fresh context, try to reclaim the same name
        context = page.context.browser.new_context()
        page2 = context.new_page()
        try:
            page2.goto(f"{base_url}/gifts/{slug}/")
            page2.wait_for_load_state("networkidle")
            page2.fill("input[name=guest_name]", guest_name)
            page2.click("button[type=submit]")
            page2.wait_for_load_state("networkidle")

            # Verify we see the name-taken page with reclaim option
            content = page2.content()
            assert "Ta nazwa jest już zajęta" in content
            assert "loguję się ponownie" in content or "To moje imię" in content

            # Submit the reclaim form — the reclaim button is the form submit
            # with name="reclaim" value="1"
            # Use page2.click for reliable navigation handling
            page2.locator("button[name=reclaim]").click()
            page2.wait_for_load_state("networkidle")

            # After reclaim, we should be on the password gate
            # Wait for the password input to appear
            password_input = page2.locator("#password")
            password_input.wait_for(timeout=5000)
            assert password_input.count() == 1, f"Password gate not shown after reclaim. URL: {page2.url}"

            # Enter the password
            page2.fill("#password", password)
            page2.click("button[type=submit]")
            page2.wait_for_load_state("networkidle")

            # Should see the gift list content
            assert "Test Gift List" in page2.content()
            assert guest_name in page2.content()
        finally:
            context.close()


class TestWrongPassword:
    """Test wrong password handling and error messages."""

    def test_wrong_password_shows_error_no_content_leak(self, page, base_url, seed_gift_list):
        """Wrong password shows error and does not leak list content."""
        slug = seed_gift_list["slug"]
        guest_name = f"WP{uuid.uuid4().hex[:6]}"

        # Pass name gate
        page.goto(f"{base_url}/gifts/{slug}/")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        # Enter wrong password
        page.fill("input[name=password]", "wrongpassword123")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        content = page.content()
        assert "Nieprawidłowe hasło" in content
        # No list content should leak
        assert "Test Gift List" not in content
        assert "Prezent" not in content
        # Password form should still be visible
        assert page.locator("input[name=password]").count() == 1

    def test_wrong_password_on_event_shows_error(self, page, base_url, seed_event):
        """Wrong password on event page shows error without leaking content."""
        slug = seed_event["slug"]
        guest_name = f"WP{uuid.uuid4().hex[:6]}"

        page.goto(f"{base_url}/events/{slug}/")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=guest_name]", guest_name)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        page.fill("input[name=password]", "wrongpassword123")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        content = page.content()
        assert "Nieprawidłowe hasło" in content
        assert "Test Event" not in content
        assert page.locator("input[name=password]").count() == 1


class TestArchivedPages:
    """Test archived list/event pages show correct message."""

    def test_archived_gift_list_shows_archived_page(self, page, base_url, seed_archived_gift_list):
        """Archived gift list shows 'archived' page after auth."""
        slug = seed_archived_gift_list["slug"]
        password = seed_archived_gift_list["password"]
        guest_name = f"AG{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "gifts")

        content = page.content()
        # Should show archived page
        assert "zarchiwizowana" in content
        # Should NOT show the normal gift list template
        assert "Przypisz" not in content
        assert "Archived Item" not in content

    def test_archived_event_shows_archived_page(self, page, base_url, seed_archived_event):
        """Archived event shows 'archived' page after auth."""
        slug = seed_archived_event["slug"]
        password = seed_archived_event["password"]
        guest_name = f"AE{uuid.uuid4().hex[:8]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "events")

        content = page.content()
        # Should show archived page
        assert "zarchiwizowana" in content
        # Should NOT show the normal event roles template
        assert "Przypisz" not in content
        assert "Archived Role" not in content

    def test_archived_page_does_not_leak_list_name(self, page, base_url, seed_archived_gift_list):
        """The archived page does not display the list/event name."""
        slug = seed_archived_gift_list["slug"]
        password = seed_archived_gift_list["password"]
        guest_name = f"AG{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "gifts")

        content = page.content()
        assert "Archived Gift List" not in content


class TestInProgressPages:
    """Test empty/in-progress list/event pages show correct message."""

    def test_empty_gift_list_shows_in_progress(self, page, base_url, seed_empty_gift_list):
        """Gift list with no items shows 'creation in progress' page after auth."""
        slug = seed_empty_gift_list["slug"]
        password = seed_empty_gift_list["password"]
        guest_name = f"EG{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "gifts")

        content = page.content()
        # Should show in-progress page
        assert "Tworzenie" in content or "tworzenia" in content or "wrócić" in content
        # Should NOT show the normal gift list template
        assert "Przypisz" not in content

    def test_empty_event_shows_in_progress(self, page, base_url, seed_empty_event):
        """Event with no roles shows 'creation in progress' page after auth."""
        slug = seed_empty_event["slug"]
        password = seed_empty_event["password"]
        guest_name = f"EE{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "events")

        content = page.content()
        # Should show in-progress page
        assert "Tworzenie" in content or "tworzenia" in content or "wrócić" in content
        # Should NOT show the normal event roles template
        assert "Przypisz" not in content


class TestGuestSessionPersistence:
    """Test that guest name persists across pages in the same session."""

    def test_guest_name_shows_in_header_after_auth(self, page, base_url, seed_gift_list):
        """After authenticating, guest name is displayed in the header."""
        slug = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"SP{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "gifts")

        # Name should be in the header
        header_text = page.locator("header").inner_text()
        assert guest_name in header_text

    def test_guest_name_persists_across_pages(self, page, base_url, seed_gift_list):
        """After setting name on one page, it persists when navigating to another."""
        slug = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"SP{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "gifts")

        # Navigate to a different page (homepage)
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")

        # Name should still be in the header
        header_text = page.locator("header").inner_text()
        assert guest_name in header_text

    def test_guest_name_persists_from_gifts_to_events(self, page, base_url, seed_gift_list, seed_event):
        """Name set on a gift list persists when visiting an event."""
        slug_gift = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"SP{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug_gift, guest_name, password, "gifts")

        # Navigate to a different event (no name gate needed)
        slug_event = seed_event["slug"]
        page.goto(f"{base_url}/events/{slug_event}/")
        page.wait_for_load_state("networkidle")

        # Since name is already set, we should see the password gate directly (no name gate)
        assert page.locator("input[name=password]").count() == 1
        assert page.locator("input[name=guest_name]").count() == 0

        # Enter event password
        page.fill("input[name=password]", seed_event["password"])
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        # Name should still be visible in header
        header_text = page.locator("header").inner_text()
        assert guest_name in header_text
        assert "Test Event" in page.content()

    def test_header_displays_guest_name_readonly(self, page, base_url, seed_gift_list):
        """The guest name in the header is displayed as read-only text."""
        slug = seed_gift_list["slug"]
        password = seed_gift_list["password"]
        guest_name = f"SP{uuid.uuid4().hex[:6]}"

        authenticate_guest(page, base_url, slug, guest_name, password, "gifts")

        header_text = page.locator("header").inner_text()
        # The name should just appear in the header as text, not as an input field
        assert guest_name in header_text
        # There shouldn't be an input for name in the header (it should be display-only)
        # But there may be a "Zmień" (Change) link/button
        # This is fine — the name itself is read-only text