
from django.conf import settings
from django.contrib import messages

from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from datetime import datetime
from dateutil import parser

from .models import CitesphereAccount, CitesphereGroup, CitesphereGroup, CitesphereCollection, CitesphereItem

import requests

def parse_iso_datetimes(datetime_list):
    parsed_dates = []
    
    for dt_str in datetime_list:
        if dt_str:
            try:
                parsed_dt = parser.isoparse(dt_str)

                if parsed_dt.tzinfo is None:
                    parsed_dt = make_aware(parsed_dt)

                # Format the date as 'YYYY-MM-DD'
                parsed_dates.append(parsed_dt.strftime('%Y-%m-%d'))

            except (ValueError, TypeError):
                parsed_dates.append(None)  # Append None if parsing fails
        else:
            parsed_dates.append(None)
    
    return parsed_dates


def get_giles_document_details(user, file_id):
    """
    Retrieve detailed information about a document from Giles for a given user and document ID.

    Args:
        user: The user object
        document_id: The ID of the document that you recieve from Citesphere Items endpoint

    Returns:
        A dictionary with the document details if successful, None otherwise.
    """
    try:
        citesphere_account = CitesphereAccount.objects.filter(user=user).first()
        if not citesphere_account:
            return None
        token = citesphere_account.access_token
        headers = {'Authorization': f'Bearer {token}'}
        url = f"{settings.GILES_ENDPOINT}api/v2/resources/files/{file_id}/content/"

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        return response.text
    except requests.RequestException as e:
        print(f"Failed to retrieve Giles document details: {e}")
        return None
    
# Functions to get Citesphere data
def get_citesphere_groups(user, request):
    """
    Utility function to fetch and store Citesphere Groups
    """
    try:
        account = CitesphereAccount.objects.get(user=user)
        response = requests.get(f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/',
                                headers={'Authorization': f'Bearer {account.access_token}'})
        if response.status_code == 200:
            groups_data = response.json()
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
            # Success message
            messages.success(request, 'Citesphere groups retrieved successfully.')
        else:
            messages.error(request, f"Failed to retrieve groups.")

    except CitesphereAccount.DoesNotExist:
        messages.error(request, "No Citesphere account associated with your account, please connect your Citesphere account to view your groups")
    except requests.RequestException as e:
        messages.error(request, f"An error occurred while retrieving groups")


def get_citesphere_collections(user, group, request):
    """
    Utility function to fetch and store Citesphere collections and items for a specific group.
    """
    account = CitesphereAccount.objects.get(user=user)
    
    try:
        # Fetch collections from Citesphere
        collections_response = requests.get(
            f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{group.group_id}/collections/',
            headers={'Authorization': f'Bearer {account.access_token}'}
        )
        if collections_response.status_code == 200:
            collections_data = collections_response.json().get('collections', [])
            
            # Fetch items for the group
            items_response = requests.get(
                f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{group.group_id}/items',
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
            
            # Process item keys after collections are updated
            for item_data in items_data:
                datetime_strings = [
                    item_data.get('date'),
                    item_data.get('dateAdded'),
                    item_data.get('dateModified')
                ]
                parsed_dates = parse_iso_datetimes(datetime_strings)

                # Unpack the parsed dates
                date, date_added, date_modified = parsed_dates
                
                # Update or create items related to this group
                CitesphereItem.objects.update_or_create(
                    key=item_data['key'],
                    group=group,
                    defaults={
                        'title': item_data['title'],
                        'authors': item_data['authors'][0]['name'] if item_data['authors'] and 'name' in item_data['authors'][0] and item_data['authors'][0]['name'] else "",
                        'itemType': item_data['itemType'],
                        'publicationTitle': item_data.get('publicationTitle', ''),
                        'volume': item_data.get('volume', ''),
                        'date': date,
                        'url': item_data.get('url', ''),
                        'dateAdded': date_added,
                        'dateModified': date_modified,
                    }
                )
                
            messages.success(request, 'Citesphere collections and items imported successfully.')
        else:
            messages.error(request, f"Failed to retrieve collections.")

    except requests.RequestException as e:
        messages.error(request, f"An error occurred while retrieving collections")