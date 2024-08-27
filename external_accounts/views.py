from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from urllib.parse import urlencode
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import CitesphereAccount, CitesphereGroup, CitesphereCollection, CitesphereItem
from django.utils import timezone
from django.utils.timezone import make_aware
from datetime import timedelta, datetime
from django.utils.dateparse import parse_datetime
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


def get_citesphere_groups(request):
    try:
        account = CitesphereAccount.objects.get(user=request.user)
        response = requests.get(f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/',
                                headers={'Authorization': f'Bearer {account.access_token}'})
        if response.status_code == 200:
            groups_data = response.json()
            print(groups_data) # DEBUG
            for group_data in groups_data:
                date_created = parse_datetime(group_data['created'])
                date_modified = parse_datetime(group_data['lastModified'])
                
                group, created = CitesphereGroup.objects.update_or_create(
                    group_id=group_data['id'],
                    defaults={
                        'name': group_data['name'],
                        'version': group_data['version'],
                        'num_items': group_data['numItems'],
                        'type': group_data['type'],
                        'description': group_data.get('description', ''),
                        'date_created': date_created,
                        'date_modified': date_modified,
                    }
                )
                # Handling the many-to-many relationship with CitesphereAccount
                group.citesphere_accounts.add(account)
            return redirect('list_citesphere_groups')
        else:
            return JsonResponse({'error': f"Failed to retrieve groups. Status code: {response.status_code}"}, status=response.status_code)
    except CitesphereAccount.DoesNotExist:
        return JsonResponse({'error': "No Citesphere account associated with this user."}, status=404)
    except requests.RequestException as e:
        return JsonResponse({'error': f"An error occurred while retrieving groups: {str(e)}"}, status=500)

def get_citesphere_collections(request, group_id):
    group = get_object_or_404(CitesphereGroup, group_id=group_id)
    account = CitesphereAccount.objects.get(user=request.user)

    try:
        # Retrieve collections
        collections_response = requests.get(
            f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{group_id}/collections/',
            headers={'Authorization': f'Bearer {account.access_token}'}
        )
        if collections_response.status_code == 200:
            collections_data = collections_response.json().get('collections', [])
            # Fetch items for the group once
            items_response = requests.get(
                f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{group_id}/items',
                headers={'Authorization': f'Bearer {account.access_token}'}
            )
            items_data = items_response.json().get('items', []) if items_response.status_code == 200 else []

            # Process each collection
            for collection_data in collections_data:
                last_modified_ts = collection_data.get('lastModified')
                last_modified_dt = make_aware(datetime.fromtimestamp(last_modified_ts / 1000)) if last_modified_ts else None
                collection, _ = CitesphereCollection.objects.update_or_create(
                    group=group,
                    key=collection_data['key'],
                    defaults={
                        'collection_id': collection_data['id']['timestamp'],
                        'name': collection_data['name'],
                        'description': collection_data.get('description', ''),
                        'version': collection_data['version'],
                        'content_version': collection_data['contentVersion'],
                        'number_of_collections': collection_data['numberOfCollections'],
                        'number_of_items': collection_data['numberOfItems'],
                        'parent_collection_key': collection_data.get('parentCollectionKey'),
                        'last_modified': last_modified_dt,
                    }
                )

            # Process items after collections are updated
            for item_data in items_data:
                date = make_aware(datetime.strptime(item_data['date'], "%Y-%m-%dT%H:%M:%SZ")) if item_data['date'] else None
                date_added = make_aware(datetime.strptime(item_data['dateAdded'], "%Y-%m-%dT%H:%M:%SZ")) if item_data['dateAdded'] else None
                date_modified = make_aware(datetime.strptime(item_data['dateModified'], "%Y-%m-%dT%H:%M:%SZ")) if item_data['dateModified'] else None
                
                # Update or create items related to this group
                CitesphereItem.objects.update_or_create(
                    key=item_data['key'],
                    group=group,
                    defaults={
                        'title': item_data['title'],
                        'authors': str(item_data['authors'][0]['name']),
                        'itemType': item_data['itemType'],
                        'publicationTitle': item_data.get('publicationTitle', ''),
                        'volume': item_data.get('volume', ''),
                        'date': date,
                        'url': item_data.get('url', ''),
                        'dateAdded': date_added,
                        'dateModified': date_modified,
                    }
                )

            return redirect('list_citesphere_groups')
        else:
            return JsonResponse({'error': f"Failed to retrieve collections. Status code: {collections_response.status_code}"}, status=collections_response.status_code)
    except requests.RequestException as e:
        return JsonResponse({'error': f"An error occurred while retrieving collections: {str(e)}"}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def list_citesphere_groups(request):
    template = 'citesphere/citesphere.html'
    account = CitesphereAccount.objects.get(user=request.user)
    groups = CitesphereGroup.objects.filter(citesphere_accounts=account)
    context = {
        'groups':groups,
    }
    return render(request, template, context)


def group_detail(request, slug):
    group = get_object_or_404(CitesphereGroup, slug=slug)
    collections = group.collections.all()
    items = group.items.all()
    template = 'citesphere/citesphere_group_detail.html'
    context = {
        'group': group,
        'collections': collections,
        'items':items,
    }
    return render(request, template, context)
