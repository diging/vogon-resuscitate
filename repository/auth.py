from django.conf import settings
from external_accounts.models import CitesphereAccount


def citesphere_auth(user):
    """
    Authenticate from Citesphere
    """
    try:
        account = CitesphereAccount.objects.get(user=user)
        return {'Authorization': f'Bearer {account.access_token}'}
    except CitesphereAccount.DoesNotExist:
        return {}


def giles_auth(user):
    """
    Build an auth header for Giles.
    """
    import giles
    return {'Authorization': 'token %s' % giles.get_user_auth_token(user)}
