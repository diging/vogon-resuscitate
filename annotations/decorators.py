from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponseForbidden
from functools import wraps

def vogon_admin_required(view_func):
    """
    Decorator for views that checks if the user is logged in and has vogon_admin access.
    """
    @wraps(view_func)
    @login_required  # Ensures the user is logged in before checking permissions, this allows us not to nest this decorator in the view
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_vogon_admin:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("You do not have permission to access this page.")
    return _wrapped_view


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
        return HttpResponseForbidden("You do not have permission to access this page.")
    return _wrapped_view
