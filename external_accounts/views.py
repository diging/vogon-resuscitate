from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode
from django.conf import settings

from django.utils.timezone import now
from datetime import timedelta

from .models import CitesphereAccount
from repository.models import Repository

import requests
import secrets

@login_required
def citesphere_login(request):
    repository_id = request.GET.get('repository_id')
    next_url = request.GET.get('next', reverse('home'))

    if not repository_id:
        return redirect('repository_list')
    repository = get_object_or_404(Repository, pk=repository_id)

    state = secrets.token_urlsafe()
    # Store state and next_url in the session
    request.session['oauth_state'] = state
    request.session['oauth_next'] = next_url
    request.session['repository_id'] = repository_id

    params = {
        'client_id': repository.client_id,
        'scope': 'read',
        'response_type': 'code',
        'redirect_uri': f"{settings.BASE_URL}oauth/callback/citesphere/",
        'state': state
    }

    url = f"{repository.endpoint}/api/oauth/authorize/?{urlencode(params)}"
    return redirect(url)

def citesphere_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')

    stored_state = request.session.get('oauth_state')
    next_url = request.session.get('oauth_next', reverse('home'))
    repository_id = request.session.get('repository_id')

    if state != stored_state:
        return render(request, 'citesphere/error.html', {
            'message': 'State mismatch error during OAuth. Possible CSRF attack.'
        })

    if error:
        return render(request, 'citesphere/error.html', {
            'message': f'Authorization failed with Citesphere. Error: {error}'
        })

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
        return render(request, 'citesphere/error.html', {
            'message': 'Failed to Authenticate. Please try again later.'
        })

    token_data = token_response.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    expires_at = now() + timedelta(seconds=int(expires_in))

    # Store the tokens in the CitesphereAccount model
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

    # Clean up session variables
    del request.session['oauth_state']
    del request.session['oauth_next']
    del request.session['repository_id']

    # Redirect back to the original page
    return redirect(next_url)

@login_required
def citesphere_refresh_token(request, repository_id):
    next_url = request.GET.get('next', reverse('home'))
    repository = get_object_or_404(Repository, pk=repository_id)
    user = request.user

    try:
        citesphere_account = CitesphereAccount.objects.get(user=user, repository=repository)
    except CitesphereAccount.DoesNotExist:
        # Redirect to login if no account exists
        return redirect(
            reverse('citesphere_login') + f'?repository_id={repository_id}&next={next_url}'
        )

    # refresh the token
    response = requests.post(f"{repository.endpoint}/api/oauth/token", data={
        'grant_type': 'refresh_token',
        'refresh_token': citesphere_account.refresh_token,
        'client_id': repository.client_id,
        'client_secret': repository.client_secret,
    })

    if response.status_code == 200:
        token_data = response.json()
        citesphere_account.access_token = token_data.get('access_token')
        citesphere_account.refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in')
        citesphere_account.token_expires_at = now() + timedelta(seconds=int(expires_in))
        citesphere_account.save()
        # Redirect back to the original page
        return redirect(next_url)
    else:
        # If refresh fails, delete the account and redirect to login
        citesphere_account.delete()
        return redirect(
            reverse('citesphere_login') + f'?repository_id={repository_id}&next={next_url}'
        )
