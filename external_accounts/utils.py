import requests
from .models import CitesphereAccount
from django.conf import settings

from django.utils.timezone import make_aware
from datetime import datetime

def parse_iso_datetimes(datetime_list):
    parsed_datetimes = []
    
    for dt_str in datetime_list:
        if dt_str:
            if dt_str.endswith('Z'):
                dt_str = dt_str.replace('Z', '+00:00')
            try:
                parsed_dt = datetime.fromisoformat(dt_str)
                parsed_datetimes.append(make_aware(parsed_dt))
            except ValueError:
                parsed_datetimes.append(None)
        else:
            parsed_datetimes.append(None)
    
    return parsed_datetimes

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