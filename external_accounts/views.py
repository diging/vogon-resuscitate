from django.shortcuts import render, redirect
from django.conf import settings
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from .models import CitesphereAccount
from django.utils import timezone
from datetime import timedelta
import requests
import secrets

def citesphere_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')

    if error:
        return render(request, 'error.html', {'message': 'Authorization failed with Citesphere.'})

    token_response = requests.post(settings.CITESPHERE_TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.CITESPHERE_REDIRECT_URI,
        'client_id': settings.CITESPHERE_CLIENT_ID,
        'client_secret': settings.CITESPHERE_CLIENT_SECRET,
    }).json()

    access_token = token_response.get('access_token')
    refresh_token = token_response.get('refresh_token')
    expires_in = token_response.get('expires_in')

    # Calculate the expiration time
    expires_at = timezone.now() + timedelta(seconds=expires_in)

    # Update or create the account instance
    citesphere_account, created = CitesphereAccount.objects.update_or_create(
        user=request.user,
        defaults={
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires_at': expires_at,
            'extra_data': token_response  # or a subset of the response
        }
    )

    return redirect('home')

@login_required
def citesphere_login(request):
    state = secrets.token_urlsafe()
    request.session['oauth_state'] = state  # Store state in user's session for later validation

    params = {
        'client_id': settings.CITESPHERE_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': settings.CITESPHERE_REDIRECT_URI,
        'scope': 'read write',
        'state': state
    }
    url = f"{settings.CITESPHERE_AUTH_URL}?{urlencode(params)}"
    return redirect(url)

@login_required
def refresh_access_token(request):
    citesphere_account = CitesphereAccount.objects.get(user=request.user)
    response = requests.post(settings.CITESPHERE_TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'refresh_token': citesphere_account.refresh_token,
        'client_id': settings.CITESPHERE_CLIENT_ID,
        'client_secret': settings.CITESPHERE_CLIENT_SECRET,
    }).json()

    new_access_token = response.get('access_token')
    new_refresh_token = response.get('refresh_token')
    expires_in = response.get('expires_in')
    expires_at = timezone.now() + timedelta(seconds=expires_in)

    # Update tokens and expiration
    citesphere_account.access_token = new_access_token
    citesphere_account.refresh_token = new_refresh_token
    citesphere_account.token_expires_at = expires_at
    citesphere_account.save()

    return new_access_token
