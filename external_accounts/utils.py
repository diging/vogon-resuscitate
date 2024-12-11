
from django.conf import settings
from django.contrib import messages

from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from datetime import datetime
from dateutil import parser

from .models import CitesphereAccount

import requests
import logging
logger = logging.getLogger(__name__)


class GilesAPI:
    """Class to handle interactions with the Giles API"""
    
    def __init__(self, user, repository):
        self.repository = repository
        self.base_url = repository.giles_endpoint
        self.user = user
        self.access_token = self._get_access_token()
        
    def _get_access_token(self):
        """Get authentication token for user"""
        try:
            account = CitesphereAccount.objects.get(user=self.user, repository=self.repository)
            return account.access_token
        except CitesphereAccount.DoesNotExist:
            return None
        
    def get_file_content(self, file_id):
        """Make request to Giles API to get file content"""
        if not self.access_token:
            raise ValueError("User must authenticate with Citesphere before making API calls")
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/api/v2/resources/files/{file_id}/content/"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text


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


def get_giles_document_details(user, file_id, repository):
    """
    Retrieve detailed information about a document from Giles for a given user and document ID.

    Args:
        user: The user object
        file_id: The ID of the file to retrieve from Giles
        repository: The repository object containing Giles endpoint info

    Returns:
        A dictionary with the document details if successful, None otherwise.
    """
    try:
        giles = GilesAPI(user, repository)
        return giles.get_file_content(file_id)
        
    except requests.RequestException as e:
        logger.error(f"Failed to retrieve Giles document details: {e}")
        return None
