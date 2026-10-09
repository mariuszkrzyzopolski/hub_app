"""Session helpers for guest name and authenticated slugs management."""


GUEST_NAME_KEY = 'guest_name'
AUTH_SLUGS_KEY = 'authenticated_slugs'


def get_guest_name(request):
    """Return the guest's session-stored name or None."""
    return request.session.get(GUEST_NAME_KEY)


def set_guest_name(request, name):
    """Store the guest name in the session."""
    request.session[GUEST_NAME_KEY] = name
    request.session.modified = True


def clear_guest_name(request):
    """Remove the guest name from the session."""
    if GUEST_NAME_KEY in request.session:
        del request.session[GUEST_NAME_KEY]
        request.session.modified = True


def get_authenticated_slugs(request):
    """Return the dict of authenticated slugs and their password versions."""
    return request.session.get(AUTH_SLUGS_KEY, {})


def add_authenticated_slug(request, slug, password_version):
    """Add a slug to the authenticated slugs list."""
    slugs = request.session.get(AUTH_SLUGS_KEY, {})
    slugs[slug] = {'password_version': password_version}
    request.session[AUTH_SLUGS_KEY] = slugs
    request.session.modified = True


def is_slug_authenticated(request, slug, current_version):
    """Check if a slug is authenticated with a matching password version."""
    slugs = request.session.get(AUTH_SLUGS_KEY, {})
    slug_data = slugs.get(slug)
    return slug_data is not None and slug_data.get('password_version') == current_version