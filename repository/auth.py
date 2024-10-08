from django.conf import settings
from external_accounts.models import CitesphereAccount

from django.shortcuts import redirect
from django.urls import reverse


def citesphere_auth(user):
    """
    Authenticate from Citesphere
    """
    try:
        account = CitesphereAccount.objects.get(user=user)
        return {'Authorization': f'Bearer {account.access_token}'}
    
    except CitesphereAccount.DoesNotExist:
        return redirect(reverse('dashboard'))  # Redirect user to dashboard to connect Citesphere account


def giles_auth(user):
    """
    Build an auth header for Giles.
    """
    import giles
    return {'Authorization': 'token %s' % giles.get_user_auth_token(user)}
