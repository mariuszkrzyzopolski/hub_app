from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.shortcuts import render
from django.contrib.auth.hashers import check_password
from django.db.models import F

from .models import GuestName
from .session import get_guest_name, set_guest_name


@method_decorator(never_cache, name='dispatch')
class PasswordGatedViewMixin:
    """
    Mixin for password-gated views.
    Must be leftmost in class inheritance chain.
    Overrides dispatch() to block unauthenticated access.
    """

    password_model = None  # Must be set by subclass
    password_template = 'core/password_gate.html'
    name_template = 'core/name_gate.html'

    def dispatch(self, request, *args, **kwargs):
        slug = kwargs.get('slug')

        # Step 1: Name gate — guest must have a name
        guest_name = get_guest_name(request)
        if not guest_name:
            if request.method == 'POST' and 'guest_name' in request.POST:
                name = request.POST['guest_name'].strip()
                if len(name) < 3:
                    return render(request, self.name_template, {
                        'error': 'Imię musi mieć co najmniej 3 znaki.',
                    })
                # Reclaim: user says it's their name, reuse it without creating new record
                if 'reclaim' in request.POST:
                    # Check if the name actually exists in the database
                    exists = GuestName.objects.filter(name=name).exists()
                    if exists:
                        set_guest_name(request, name)
                        request.session.modified = True
                        if slug:
                            return self._check_password_gate(request, slug)
                        return super().dispatch(request, *args, **kwargs)
                    # If name doesn't exist (e.g. someone deleted it), fall through to normal flow
                try:
                    GuestName.objects.create(name=name)
                except Exception:
                    from .names_recommendation import suggest_names
                    suggestions = suggest_names(name)
                    return render(request, self.name_template, {
                        'error': 'Ta nazwa jest już zajęta.',
                        'suggestions': suggestions,
                        'slug': slug,
                        'name_taken': True,
                        'submitted_name': name,
                    })
                set_guest_name(request, name)
                request.session.modified = True
                if slug:
                    return self._check_password_gate(request, slug)
                return super().dispatch(request, *args, **kwargs)

            return render(request, self.name_template, {'slug': slug})

        # Step 2: Password gate
        if slug:
            return self._check_password_gate(request, slug)

        return super().dispatch(request, *args, **kwargs)

    def _check_password_gate(self, request, slug):
        """Check if the guest has authenticated for this slug."""
        obj = self._get_password_model_obj(slug)
        if not obj:
            from django.http import Http404
            raise Http404("Not found")

        authenticated_slugs = request.session.get('authenticated_slugs', {})
        slug_data = authenticated_slugs.get(slug)

        # Check if already authenticated with current password version
        if slug_data and slug_data.get('password_version') == obj.password_version:
            return super().dispatch(request, slug=slug)

        # Show password form
        if request.method == 'POST' and 'password' in request.POST:
            password = request.POST['password']
            from django.contrib.auth.hashers import check_password as django_check
            if django_check(password, obj.password_hash):
                authenticated_slugs[slug] = {
                    'password_version': obj.password_version,
                }
                request.session['authenticated_slugs'] = authenticated_slugs
                request.session.modified = True
                return super().dispatch(request, slug=slug)

            # Track failed attempts
            failed = request.session.get('failed_attempts', {})
            failed[slug] = failed.get(slug, 0) + 1
            request.session['failed_attempts'] = failed
            request.session.modified = True

            # Log 3 consecutive failures
            if failed[slug] >= 3:
                self._log_failed_auth(request, slug, obj)

            return render(request, self.password_template, {
                'error': 'Nieprawidłowe hasło.',
                'slug': slug,
            })

        return render(request, self.password_template, {'slug': slug})

    def _get_password_model_obj(self, slug):
        if self.password_model:
            return self.password_model.objects.filter(slug=slug).first()
        return None

    def _log_failed_auth(self, request, slug, obj):
        """Log failed authentication attempts. Override in subclass."""
        pass