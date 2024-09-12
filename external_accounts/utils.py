import requests
from .models import CitesphereAccount
from django.conf import settings


def get_giles_document_details(user, document_id):
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
        headers = {'Authorization': f'Token {token}'}
        url = f"{settings.GILES_ENDPOINT}/api/v2/resources/documents/{document_id}"

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        return response.json()
    except requests.RequestException as e:
        print(f"Failed to retrieve Giles document details: {e}")
        return None