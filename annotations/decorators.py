from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps

def vogon_admin_or_staff_required(view_func):
    """
    Decorator for views that checks if the user is logged in and has either
    vogon_admin or staff access.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_vogon_admin or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("You do not have permission to access this page.")
    return _wrapped_view

# Django does not provide a dedicated built-in decorator specifically for admins
def admin_required(view_func):
    """
    Decorator for views that checks if the user is logged in as the django admin.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("You do not have permission to access this page.")
    return _wrapped_view