from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from .models import CitesphereAccount
from django.utils import timezone
from datetime import timedelta
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

    print("tojen: ", token_response)

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

def list_resources(request, group_id=None, collection_id=None):
    try:
        # Retrieve the access token from user's associated CitesphereAccount or session
        if group_id is None:
            account = CitesphereAccount.objects.get(user=request.user)
            access_token = account.access_token
        else:
            access_token = request.session.get('access_token')

        # Build the appropriate URL based on what parameters are provided
        if collection_id:
            url = f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{group_id}/collections/{collection_id}/texts'
        elif group_id:
            url = f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{group_id}/collections'
        else:
            url = f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups'

        # Make the request to the Citesphere API
        response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
        if response.status_code == 200:
            data = response.json()
            return render(request, 'list_resources.html', {'data': data, 'type': 'texts' if collection_id else 'collections' if group_id else 'groups', 'group_id': group_id, 'collection_id': collection_id})
        else:
            return HttpResponse(f"Failed to retrieve data. Status code: {response.status_code}", status=502)

    except CitesphereAccount.DoesNotExist:
        return HttpResponse("No Citesphere account associated with this user.", status=404)
    except KeyError:
        return HttpResponse("Access token not found in session.", status=404)
    except requests.RequestException as e:
        return HttpResponse(f"An error occurred while retrieving data: {str(e)}", status=500)