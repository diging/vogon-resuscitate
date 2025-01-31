from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import ConceptpowerAccount
from functools import wraps


def conceptpower_login_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        print("innnnnn conceptpower_authenticated")
        print(request)
        user = request.user
        try:
            conceptpower_account = ConceptpowerAccount.objects.get(user=user)
            if not conceptpower_account:
                # Redirect to login page
                return redirect(
                    reverse('conceptpower_login') + f'?next={request.path}'
                )
        except ConceptpowerAccount.DoesNotExist:
            # Redirect to Citesphere login page
            return redirect(
                reverse('conceptpower_login') + f'?next={request.path}'
            )

        # Proceed to the view
        return view_func(request, *args, **kwargs)
    return _wrapped_view