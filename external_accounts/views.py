from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode
from django.conf import settings

from django.utils import timezone
from datetime import timedelta

from .models import CitesphereAccount
from repository.models import Repository

import requests
import secrets


@login_required
def citesphere_login(request):
    repository_id = request.GET.get('repository_id')
    if not repository_id:
        return redirect('repository_list')
    repository = get_object_or_404(Repository, pk=repository_id)

    state = secrets.token_urlsafe()
    # Store state and repository_id in user's session for later validation
    request.session['oauth_state'] = state
    request.session['repository_id'] = repository_id

    params = {
        'client_id': repository.client_id,
        'scope': 'read',
        'response_type': 'code',
        'redirect_uri': f"{settings.BASE_URL}/oauth/callback/citesphere/",
        'state': state
    }

    url = f"{repository.endpoint}/api/oauth/authorize/?{urlencode(params)}"
    return redirect(url)

def citesphere_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')

    # Retrieve the repository ID and state from the session
    repository_id = request.session.get('repository_id')
    stored_state = request.session.get('oauth_state')

    # Validate state to prevent CSRF attacks
    if state != stored_state:
        return render(request, 'citesphere/error.html', {'message': 'State mismatch error during OAuth. Possible CSRF attack.'})

    # Check if there is an error in the OAuth flow
    if error:
        return render(request, 'citesphere/error.html', {'message': f'Authorization failed with Citesphere. Error: {error}'})

    # Retrieve the repository for the OAuth process
    repository = get_object_or_404(Repository, pk=repository_id)
    citesphere_redirect_uri = f"{settings.BASE_URL}oauth/callback/citesphere/"

    token_response = requests.post(f"{repository.endpoint}/api/oauth/token", data={
        'client_id': repository.client_id,
        'client_secret': repository.client_secret,
        'code': code,
        'redirect_uri': citesphere_redirect_uri,
        'grant_type': 'authorization_code',
    })

    if token_response.status_code != 200:
        return render(request, 'citesphere/error.html', {'message': 'Failed to Authenticate. Please try again later.'})

    token_data = token_response.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    expires_at = timezone.now() + timedelta(seconds=int(expires_in))

    # Store the tokens in the CitesphereAccount model, linked to the user and repository
    CitesphereAccount.objects.update_or_create(
        user=request.user,
        repository=repository,
        defaults={
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires_at': expires_at,
            'extra_data': token_data
        }
    )

    # Mark the user as authenticated with Citesphere in the session
    request.session['citesphere_authenticated'] = True

    # Redirect back to the repository details page using the repository ID
    return redirect(reverse('repository_details', args=[repository_id]))
