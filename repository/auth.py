from external_accounts.models import CitesphereAccount
from django.shortcuts import redirect
from django.urls import reverse


def citesphere_auth(user, repository):
    """
    Authenticate from Citesphere for a specific repository.

    Parameters
    ----------
    user : User object
        The user for which authentication is handled.
    repository : Repository object
        The repository for which the authentication token is needed.
    """
    try:
        # Fetch the CitesphereAccount associated with the user and repository.
        account = CitesphereAccount.objects.get(user=user, repository=repository)
        return {'Authorization': f'Bearer {account.access_token}'}
    
    except CitesphereAccount.DoesNotExist:
        # Redirect user to the dashboard to connect their Citesphere account if no valid account is found.
        return redirect(reverse('dashboard'))


def giles_auth(user):
    """
    Build an auth header for Giles.
    """
    import giles
    return {'Authorization': 'token %s' % giles.get_user_auth_token(user)}
