from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required

from .models import CitesphereAccount, ConceptpowerAccount
from repository.models import Repository

def citesphere_authenticated(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        repository_id = kwargs.get('repository_id')
        user = request.user

        if not repository_id:
            # Handle missing repository_id
            return redirect('repository_list')

        repository = Repository.objects.get(pk=repository_id)
        try:
            citesphere_account = CitesphereAccount.objects.get(user=user, repository=repository)
            if citesphere_account.is_token_expired():
                # Redirect to token refresh view
                return redirect(
                    reverse('citesphere_refresh_token', args=[repository_id]) + f'?next={request.path}'
                )
        except CitesphereAccount.DoesNotExist:
            # Redirect to Citesphere login page
            return redirect(
                reverse('citesphere_login') + f'?repository_id={repository_id}&next={request.path}'
            )

        # Proceed to the view
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def conceptpower_authenticated(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        user = request.user
        try:
            conceptpower_account = ConceptpowerAccount.objects.get(user=user)
            if not conceptpower_account:
                # Redirect to login page
                return redirect(
                    reverse('citesphere_login') + f'?next={request.path}'
                )
        except ConceptpowerAccount.DoesNotExist:
            # Redirect to Citesphere login page
            return redirect(
                reverse('citesphere_login') + f'?next={request.path}'
            )

        # Proceed to the view
        return view_func(request, *args, **kwargs)
    return _wrapped_view