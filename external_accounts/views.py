from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode
from django.conf import settings

from django.utils import timezone
from datetime import timedelta

from .models import CitesphereAccount, CitesphereGroup
from .utils import get_citesphere_groups, get_citesphere_collections

import requests
import secrets

@login_required
def citesphere_login(request):
    state = secrets.token_urlsafe()
    request.session['oauth_state'] = state  # Store state in user's session for later validation

    params = {
        'client_id': settings.CITESPHERE_CLIENT_ID,
        'scope': 'read',
        'response_type': 'code',
        'state': state
    }
    url = f"{settings.CITESPHERE_AUTH_URL}?{urlencode(params)}"
    return redirect(url)

def citesphere_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')

    if error:
        return render(request, 'error.html', {'message': 'Authorization failed with Citesphere.'})

    token_response = requests.post(settings.CITESPHERE_TOKEN_URL, data={
        'client_id': settings.CITESPHERE_CLIENT_ID,
        'client_secret': settings.CITESPHERE_CLIENT_SECRET,
        'code': code,
        'redirect_uri': settings.CITESPHERE_REDIRECT_URI,
        'state': state,
        'grant_type': 'authorization_code',
    }).json()

    access_token = token_response.get('access_token')
    refresh_token = token_response.get('refresh_token')
    expires_in = token_response.get('expires_in')

    # Calculate the expiration time
    expires_at = expires_at = timezone.now() + timedelta(seconds=int(expires_in))

    # Update or create the account instance
    citesphere_account, created = CitesphereAccount.objects.update_or_create(
        user=request.user,
        defaults={
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires_at': expires_at,
            'extra_data': token_response
        }
    )

    return redirect('home')

@login_required
def list_citesphere_groups(request):
    template = 'citesphere/citesphere.html'

    get_citesphere_groups(request.user, request)

    account = CitesphereAccount.objects.get(user=request.user)
    groups = CitesphereGroup.objects.filter(citesphere_accounts=account)
    context = {
        'groups':groups,
    }
    return render(request, template, context)

@login_required
def group_detail(request, slug):
    print("GROUP DETAIL", slug)
    group = get_object_or_404(CitesphereGroup, slug=slug)

    get_citesphere_collections(request.user, group, request)

    collections = group.collections.all()
    items = group.items.all()

    template = 'citesphere/citesphere_group_detail.html'
    context = {
        'group': group,
        'collections': collections,
        'items': items,
        'slug': slug,
    }
    return render(request, template, context)
