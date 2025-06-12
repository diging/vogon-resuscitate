from django.conf import settings
from .models import CitesphereAccount

from repository.exceptions import GilesTextExtractionError

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
        
    def giles_is_file_processing(self, progress_id):
        """
        Returns True if the file is still processing, False otherwise.
        """
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        url = f"{self.base_url}/api/v2/files/upload/check/{progress_id}/"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # check if the document has status of not COMPLETE to return True
        return data[0].get('documentStatus') != 'COMPLETE'

    def get_file_content(self, file_id):
        """
        Get the content of a file from the Giles API.

        Args:
            file_id: ID of the file to retrieve content for

        Returns:
            String containing the file content for text files, or raw bytes for binary files

        Raises:
            ValueError: If user is not authenticated with Citesphere
            HTTPError: If API request fails
        """
        if not self.access_token:
            raise ValueError("User must authenticate with Citesphere before making API calls")
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/api/v2/resources/files/{file_id}/content/"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Get content type from response headers and store it
        content_type = response.headers.get('content-type', '').lower()
        self._last_response_content_type = content_type
        
        # For text files, return as text
        if content_type.startswith('text/'):
            content = response.text
            # Some text files have null characters in them, which causes issues with the text extraction
            if '\x00' in content:
                logger.error("Null character found in file content")
                raise GilesTextExtractionError("File content contains null characters")
            return content
        else:
            return response.content


